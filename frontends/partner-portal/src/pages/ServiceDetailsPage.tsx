import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  addMarketplaceServiceLocation,
  addMarketplaceServiceMedia,
  addMarketplaceServiceScheduleException,
  addMarketplaceServiceScheduleRule,
  archiveMarketplaceService,
  fetchMarketplaceService,
  fetchMarketplaceServiceAvailability,
  fetchMarketplaceServiceLocations,
  fetchMarketplaceServiceSchedule,
  removeMarketplaceServiceLocation,
  removeMarketplaceServiceMedia,
  removeMarketplaceServiceScheduleException,
  removeMarketplaceServiceScheduleRule,
  submitMarketplaceService,
  updateMarketplaceService,
} from "../api/marketplaceServices";
import { fetchPartnerLocationsV1, type PartnerLocationV1 } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate } from "../utils/format";
import { canManageServices, canReadServices } from "../utils/roles";
import { resolveEffectivePartnerRoles } from "../access/partnerWorkspace";
import type {
  MarketplaceService,
  MarketplaceServiceAvailabilitySlot,
  MarketplaceServiceLocation,
  MarketplaceServiceSchedule,
} from "../types/marketplace";

type TabKey = "main" | "media" | "locations" | "schedule" | "preview";

const buildDefaultForm = (service?: MarketplaceService | null) => ({
  title: service?.title ?? "",
  category: service?.category ?? "",
  description: service?.description ?? "",
  duration_min: service?.duration_min ? String(service.duration_min) : "60",
  requirements: service?.requirements ?? "",
  tags: service?.tags?.join(", ") ?? "",
  attributes: service?.attributes ? JSON.stringify(service.attributes, null, 2) : "{}",
});

const toDateInputValue = (value: Date) => value.toISOString().slice(0, 10);

export function ServiceDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { portal } = usePortal();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const effectiveRoles = resolveEffectivePartnerRoles(portal, user?.roles);
  const canRead = canReadServices(effectiveRoles);
  const canManage = canManageServices(effectiveRoles);
  const [tab, setTab] = useState<TabKey>("main");
  const [service, setService] = useState<MarketplaceService | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [form, setForm] = useState(buildDefaultForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [mediaForm, setMediaForm] = useState({ attachment_id: "", bucket: "", path: "" });
  const [locations, setLocations] = useState<MarketplaceServiceLocation[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [locationsError, setLocationsError] = useState<string | null>(null);
  const [stations, setStations] = useState<PartnerLocationV1[]>([]);
  const [stationsError, setStationsError] = useState<string | null>(null);
  const [selectedStation, setSelectedStation] = useState("");
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [schedule, setSchedule] = useState<MarketplaceServiceSchedule | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState({
    weekday: "0",
    time_from: "09:00",
    time_to: "18:00",
    slot_duration_min: "60",
    capacity: "1",
  });
  const [exceptionForm, setExceptionForm] = useState({
    date: toDateInputValue(new Date()),
    is_closed: false,
    time_from: "",
    time_to: "",
    capacity_override: "",
  });
  const [availability, setAvailability] = useState<MarketplaceServiceAvailabilitySlot[]>([]);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [availabilityRange, setAvailabilityRange] = useState(() => {
    const today = new Date();
    const end = new Date();
    end.setDate(today.getDate() + 6);
    return { from: toDateInputValue(today), to: toDateInputValue(end) };
  });
  const weekdayLabels = [
    t("serviceDetailsPage.schedule.weekdays.mon"),
    t("serviceDetailsPage.schedule.weekdays.tue"),
    t("serviceDetailsPage.schedule.weekdays.wed"),
    t("serviceDetailsPage.schedule.weekdays.thu"),
    t("serviceDetailsPage.schedule.weekdays.fri"),
    t("serviceDetailsPage.schedule.weekdays.sat"),
    t("serviceDetailsPage.schedule.weekdays.sun"),
  ];

  useEffect(() => {
    if (!user || !id || !canRead) return;
    setLoading(true);
    setError(null);
    fetchMarketplaceService(user.token, id)
      .then((data) => {
        setService(data);
        setForm(buildDefaultForm(data));
      })
      .catch((err) => {
        console.error(err);
        setError(t("serviceDetailsPage.errors.loadFailed"));
      })
      .finally(() => setLoading(false));
  }, [user, id, canRead, t, retryKey]);

  useEffect(() => {
    if (!user || !id || !canRead) return;
    setLocationsLoading(true);
    setLocationsError(null);
    fetchMarketplaceServiceLocations(user.token, id)
      .then((data) => {
        setLocations(data);
        if (data.length > 0 && !selectedLocationId) {
          setSelectedLocationId(data[0].id);
        }
      })
      .catch((err) => {
        console.error(err);
        setLocationsError(t("serviceDetailsPage.errors.loadFailed"));
      })
      .finally(() => setLocationsLoading(false));
  }, [user, id, canRead, selectedLocationId, retryKey, t]);

  useEffect(() => {
    if (!user || !canRead) return;
    setStationsError(null);
    fetchPartnerLocationsV1(user.token)
      .then((data) => setStations(data ?? []))
      .catch((err) => {
        console.error(err);
        setStationsError(t("serviceDetailsPage.errors.loadFailed"));
      });
  }, [user, canRead, retryKey, t]);

  useEffect(() => {
    if (!user || !selectedLocationId) return;
    setScheduleLoading(true);
    setScheduleError(null);
    fetchMarketplaceServiceSchedule(user.token, selectedLocationId)
      .then((data) => setSchedule(data))
      .catch((err) => {
        console.error(err);
        setScheduleError(t("serviceDetailsPage.errors.loadFailed"));
      })
      .finally(() => setScheduleLoading(false));
  }, [user, selectedLocationId, retryKey, t]);

  useEffect(() => {
    if (!user || !id || !canRead || tab !== "preview") return;
    setAvailabilityLoading(true);
    setAvailabilityError(null);
    fetchMarketplaceServiceAvailability(user.token, id, availabilityRange.from, availabilityRange.to)
      .then((data) => setAvailability(data.items ?? []))
      .catch((err) => {
        console.error(err);
        setAvailabilityError(t("serviceDetailsPage.errors.loadFailed"));
      })
      .finally(() => setAvailabilityLoading(false));
  }, [user, id, canRead, tab, availabilityRange, retryKey, t]);

  const selectedLocation = useMemo(
    () => locations.find((location) => location.id === selectedLocationId) ?? null,
    [locations, selectedLocationId],
  );

  if (!canRead) {
    return <ForbiddenState />;
  }

  if (loading) {
    return <LoadingState label={t("serviceDetailsPage.title")} />;
  }

  if (error || !service) {
    return (
      <ErrorState
        title={t("serviceDetailsPage.title")}
        description={error ?? undefined}
        action={
          <button type="button" className="secondary" onClick={() => setRetryKey((value) => value + 1)}>
            {t("actions.refresh")}
          </button>
        }
      />
    );
  }

  const handleSave = async () => {
    if (!user || !service) return;
    if (!form.title.trim() || !form.category.trim()) {
      setFormError(t("serviceDetailsPage.errors.requiredFields"));
      return;
    }
    const durationValue = Number(form.duration_min);
    if (Number.isNaN(durationValue) || durationValue < 5) {
      setFormError(t("serviceDetailsPage.errors.invalidDuration"));
      return;
    }
    let attributes = {};
    try {
      attributes = form.attributes ? JSON.parse(form.attributes) : {};
    } catch {
      setFormError(t("serviceDetailsPage.errors.invalidAttributes"));
      return;
    }
    setFormError(null);
    try {
      const updated = await updateMarketplaceService(user.token, service.id, {
        title: form.title.trim(),
        description: form.description.trim() || null,
        category: form.category.trim(),
        tags: form.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        attributes,
        duration_min: durationValue,
        requirements: form.requirements.trim() || null,
      });
      setService(updated);
    } catch (err) {
      console.error(err);
      setFormError(t("serviceDetailsPage.errors.saveFailed"));
    }
  };

  const handleSubmit = async () => {
    if (!user || !service) return;
    try {
      const updated = await submitMarketplaceService(user.token, service.id);
      setService(updated);
    } catch (err) {
      console.error(err);
      setFormError(t("serviceDetailsPage.errors.submitFailed"));
    }
  };

  const handleArchive = async () => {
    if (!user || !service) return;
    try {
      const updated = await archiveMarketplaceService(user.token, service.id);
      setService(updated);
    } catch (err) {
      console.error(err);
      setFormError(t("serviceDetailsPage.errors.archiveFailed"));
    }
  };

  const handleAddMedia = async () => {
    if (!user || !service) return;
    if (!mediaForm.attachment_id.trim() || !mediaForm.bucket.trim() || !mediaForm.path.trim()) {
      return;
    }
    try {
      await addMarketplaceServiceMedia(user.token, service.id, mediaForm);
      const refreshed = await fetchMarketplaceService(user.token, service.id);
      setService(refreshed);
      setMediaForm({ attachment_id: "", bucket: "", path: "" });
    } catch (err) {
      console.error(err);
    }
  };

  const handleRemoveMedia = async (attachmentId: string) => {
    if (!user || !service) return;
    await removeMarketplaceServiceMedia(user.token, service.id, attachmentId);
    const refreshed = await fetchMarketplaceService(user.token, service.id);
    setService(refreshed);
  };

  const handleAddLocation = async () => {
    if (!user || !service || !selectedStation) return;
    const created = await addMarketplaceServiceLocation(user.token, service.id, {
      location_id: selectedStation,
      is_active: true,
    });
    setLocations((prev) => [...prev, created]);
    setSelectedStation("");
    if (!selectedLocationId) {
      setSelectedLocationId(created.id);
    }
  };

  const handleRemoveLocation = async (serviceLocationId: string) => {
    if (!user || !service) return;
    await removeMarketplaceServiceLocation(user.token, service.id, serviceLocationId);
    setLocations((prev) => prev.filter((item) => item.id !== serviceLocationId));
    if (selectedLocationId === serviceLocationId) {
      setSelectedLocationId(null);
    }
  };

  const handleAddRule = async () => {
    if (!user || !selectedLocationId) return;
    const payload = {
      weekday: Number(ruleForm.weekday),
      time_from: ruleForm.time_from,
      time_to: ruleForm.time_to,
      slot_duration_min: Number(ruleForm.slot_duration_min),
      capacity: Number(ruleForm.capacity),
    };
    const created = await addMarketplaceServiceScheduleRule(user.token, selectedLocationId, payload);
    setSchedule((prev) =>
      prev ? { ...prev, rules: [...prev.rules, created] } : { rules: [created], exceptions: [] },
    );
  };

  const handleRemoveRule = async (ruleId: string) => {
    if (!user || !selectedLocationId) return;
    await removeMarketplaceServiceScheduleRule(user.token, selectedLocationId, ruleId);
    setSchedule((prev) => (prev ? { ...prev, rules: prev.rules.filter((rule) => rule.id !== ruleId) } : prev));
  };

  const handleAddException = async () => {
    if (!user || !selectedLocationId) return;
    const payload = {
      date: exceptionForm.date,
      is_closed: exceptionForm.is_closed,
      time_from: exceptionForm.time_from || null,
      time_to: exceptionForm.time_to || null,
      capacity_override: exceptionForm.capacity_override ? Number(exceptionForm.capacity_override) : null,
    };
    const created = await addMarketplaceServiceScheduleException(user.token, selectedLocationId, payload);
    setSchedule((prev) =>
      prev ? { ...prev, exceptions: [...prev.exceptions, created] } : { rules: [], exceptions: [created] },
    );
  };

  const handleRemoveException = async (exceptionId: string) => {
    if (!user || !selectedLocationId) return;
    await removeMarketplaceServiceScheduleException(user.token, selectedLocationId, exceptionId);
    setSchedule((prev) =>
      prev ? { ...prev, exceptions: prev.exceptions.filter((item) => item.id !== exceptionId) } : prev,
    );
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{service.title}</h2>
            <div className="muted">{t("serviceDetailsPage.meta.updated", { date: formatDate(service.updated_at ?? service.created_at ?? null) })}</div>
          </div>
          <div className="stack-inline">
            <StatusBadge status={service.status} />
            <button type="button" className="secondary" onClick={() => navigate("/services")}>
              {t("common.back")}
            </button>
          </div>
        </div>
        {formError ? (
          <div className="error" role="alert">
            {formError}
          </div>
        ) : null}
        <div className="tabs">
          {[
            { key: "main", label: t("serviceDetailsPage.tabs.main") },
            { key: "media", label: t("serviceDetailsPage.tabs.media") },
            { key: "locations", label: t("serviceDetailsPage.tabs.locations") },
            { key: "schedule", label: t("serviceDetailsPage.tabs.schedule") },
            { key: "preview", label: t("serviceDetailsPage.tabs.preview") },
          ].map((item) => (
            <button
              key={item.key}
              type="button"
              className={tab === item.key ? "tab active" : "tab"}
              onClick={() => setTab(item.key as TabKey)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {tab === "main" ? (
          <div className="stack">
            <label className="field">
              <span>{t("serviceDetailsPage.fields.title")}</span>
              <input
                type="text"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.category")}</span>
              <input
                type="text"
                value={form.category}
                onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.description")}</span>
              <textarea
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.duration")}</span>
              <input
                type="number"
                min={5}
                max={1440}
                value={form.duration_min}
                onChange={(event) => setForm((prev) => ({ ...prev, duration_min: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.requirements")}</span>
              <input
                type="text"
                value={form.requirements}
                onChange={(event) => setForm((prev) => ({ ...prev, requirements: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.tags")}</span>
              <input
                type="text"
                value={form.tags}
                onChange={(event) => setForm((prev) => ({ ...prev, tags: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            <label className="field">
              <span>{t("serviceDetailsPage.fields.attributes")}</span>
              <textarea
                value={form.attributes}
                onChange={(event) => setForm((prev) => ({ ...prev, attributes: event.target.value }))}
                disabled={!canManage || service.status !== "DRAFT"}
              />
            </label>
            {canManage ? (
              <div className="stack-inline">
                <button type="button" className="primary" onClick={handleSave} disabled={service.status !== "DRAFT"}>
                  {t("actions.save")}
                </button>
                {service.status === "DRAFT" ? (
                  <button type="button" className="secondary" onClick={handleSubmit}>
                    {t("actions.submit")}
                  </button>
                ) : null}
                {service.status !== "ARCHIVED" ? (
                  <button type="button" className="danger" onClick={handleArchive}>
                    {t("actions.archive")}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
        {tab === "media" ? (
          <div className="stack">
            <div className="muted">{t("serviceDetailsPage.hints.mediaUpload")}</div>
            <div className="stack-inline">
              <input
                type="text"
                placeholder={t("serviceDetailsPage.media.placeholders.attachmentId")}
                value={mediaForm.attachment_id}
                onChange={(event) => setMediaForm((prev) => ({ ...prev, attachment_id: event.target.value }))}
              />
              <input
                type="text"
                placeholder={t("serviceDetailsPage.media.placeholders.storage")}
                value={mediaForm.bucket}
                onChange={(event) => setMediaForm((prev) => ({ ...prev, bucket: event.target.value }))}
              />
              <input
                type="text"
                placeholder={t("serviceDetailsPage.media.placeholders.filePath")}
                value={mediaForm.path}
                onChange={(event) => setMediaForm((prev) => ({ ...prev, path: event.target.value }))}
              />
              <button type="button" className="secondary" onClick={handleAddMedia} disabled={!canManage}>
                {t("actions.add")}
              </button>
            </div>
            {service.media.length === 0 ? (
              <EmptyState
                title={t("serviceDetailsPage.empty.mediaTitle")}
                description={t("serviceDetailsPage.empty.mediaDescription")}
              />
            ) : (
              <ul className="list">
                {service.media.map((item) => (
                  <li key={item.attachment_id} className="list-item">
                    <div>
                      <strong>{item.path}</strong>
                      <div className="muted">{item.bucket}</div>
                    </div>
                    {canManage ? (
                      <button type="button" className="danger" onClick={() => handleRemoveMedia(item.attachment_id)}>
                        {t("actions.delete")}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
        {tab === "locations" ? (
          <div className="stack">
            {locationsError || stationsError ? (
              <ErrorState
                title={t("serviceDetailsPage.tabs.locations")}
                description={locationsError ?? stationsError ?? undefined}
                action={
                  <button type="button" className="secondary" onClick={() => setRetryKey((value) => value + 1)}>
                    {t("actions.refresh")}
                  </button>
                }
              />
            ) : null}
            {locationsLoading ? <LoadingState label={t("serviceDetailsPage.tabs.locations")} /> : null}
            <div className="stack-inline">
              <select value={selectedStation} onChange={(event) => setSelectedStation(event.target.value)}>
                <option value="">{t("serviceDetailsPage.schedule.selectStation")}</option>
                {stations.map((station) => (
                  <option key={station.id} value={station.id}>
                    {station.title} — {station.address}
                  </option>
                ))}
              </select>
              <button type="button" className="secondary" onClick={handleAddLocation} disabled={!canManage}>
                {t("serviceDetailsPage.actions.addLocation")}
              </button>
            </div>
            {locations.length === 0 ? (
              <EmptyState
                title={t("serviceDetailsPage.empty.locationsTitle")}
                description={t("serviceDetailsPage.empty.locationsDescription")}
              />
            ) : (
              <ul className="list">
                {locations.map((location) => (
                  <li key={location.id} className="list-item">
                    <div>
                      <strong>{location.address ?? location.location_id}</strong>
                      <div className="muted">{t("serviceDetailsPage.meta.locationId", { id: location.location_id })}</div>
                    </div>
                    {canManage ? (
                      <button type="button" className="danger" onClick={() => handleRemoveLocation(location.id)}>
                        {t("actions.delete")}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
        {tab === "schedule" ? (
          <div className="stack">
            <div className="stack-inline">
              <label className="field">
                <span>{t("serviceDetailsPage.fields.location")}</span>
                <select
                  value={selectedLocationId ?? ""}
                  onChange={(event) => setSelectedLocationId(event.target.value || null)}
                >
                  <option value="">{t("serviceDetailsPage.schedule.selectLocation")}</option>
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.address ?? location.location_id}
                    </option>
                  ))}
                </select>
              </label>
              {selectedLocation ? (
                <span className="muted">{t("serviceDetailsPage.meta.locationId", { id: selectedLocation.location_id })}</span>
              ) : null}
            </div>
            {scheduleLoading ? <LoadingState label={t("serviceDetailsPage.tabs.schedule")} /> : null}
            {scheduleError ? (
              <ErrorState
                title={t("serviceDetailsPage.tabs.schedule")}
                description={scheduleError}
                action={
                  <button type="button" className="secondary" onClick={() => setRetryKey((value) => value + 1)}>
                    {t("actions.refresh")}
                  </button>
                }
              />
            ) : null}
            {selectedLocationId ? (
              <>
                <div className="card-section">
                  <h4>{t("serviceDetailsPage.schedule.weeklyRules")}</h4>
                  <div className="stack-inline">
                    <select
                      value={ruleForm.weekday}
                      onChange={(event) => setRuleForm((prev) => ({ ...prev, weekday: event.target.value }))}
                    >
                      {weekdayLabels.map((label, index) => (
                        <option key={label} value={index}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="time"
                      value={ruleForm.time_from}
                      onChange={(event) => setRuleForm((prev) => ({ ...prev, time_from: event.target.value }))}
                    />
                    <input
                      type="time"
                      value={ruleForm.time_to}
                      onChange={(event) => setRuleForm((prev) => ({ ...prev, time_to: event.target.value }))}
                    />
                    <input
                      type="number"
                      min={5}
                      value={ruleForm.slot_duration_min}
                      onChange={(event) => setRuleForm((prev) => ({ ...prev, slot_duration_min: event.target.value }))}
                    />
                    <input
                      type="number"
                      min={1}
                      value={ruleForm.capacity}
                      onChange={(event) => setRuleForm((prev) => ({ ...prev, capacity: event.target.value }))}
                    />
                    <button type="button" className="secondary" onClick={handleAddRule} disabled={!canManage}>
                      {t("serviceDetailsPage.actions.addRule")}
                    </button>
                  </div>
                  {schedule?.rules?.length ? (
                    <ul className="list">
                      {schedule.rules.map((rule) => (
                        <li key={rule.id} className="list-item">
                          <div>
                            {t("serviceDetailsPage.schedule.ruleSummary", {
                              day: weekdayLabels[rule.weekday],
                              from: rule.time_from,
                              to: rule.time_to,
                              duration: rule.slot_duration_min,
                              capacity: rule.capacity,
                            })}
                          </div>
                          {canManage ? (
                            <button type="button" className="danger" onClick={() => handleRemoveRule(rule.id)}>
                              {t("actions.delete")}
                            </button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState
                      title={t("serviceDetailsPage.empty.rulesTitle")}
                      description={t("serviceDetailsPage.empty.rulesDescription")}
                    />
                  )}
                </div>
                <div className="card-section">
                  <h4>{t("serviceDetailsPage.schedule.exceptions")}</h4>
                  <div className="stack-inline">
                    <input
                      type="date"
                      value={exceptionForm.date}
                      onChange={(event) => setExceptionForm((prev) => ({ ...prev, date: event.target.value }))}
                    />
                    <label className="stack-inline">
                      <input
                        type="checkbox"
                        checked={exceptionForm.is_closed}
                        onChange={(event) => setExceptionForm((prev) => ({ ...prev, is_closed: event.target.checked }))}
                      />
                      <span>{t("serviceDetailsPage.schedule.closed")}</span>
                    </label>
                    <input
                      type="time"
                      value={exceptionForm.time_from}
                      onChange={(event) => setExceptionForm((prev) => ({ ...prev, time_from: event.target.value }))}
                      disabled={exceptionForm.is_closed}
                    />
                    <input
                      type="time"
                      value={exceptionForm.time_to}
                      onChange={(event) => setExceptionForm((prev) => ({ ...prev, time_to: event.target.value }))}
                      disabled={exceptionForm.is_closed}
                    />
                    <input
                      type="number"
                      min={1}
                      placeholder={t("serviceDetailsPage.schedule.capacityPlaceholder")}
                      value={exceptionForm.capacity_override}
                      onChange={(event) => setExceptionForm((prev) => ({ ...prev, capacity_override: event.target.value }))}
                      disabled={exceptionForm.is_closed}
                    />
                    <button type="button" className="secondary" onClick={handleAddException} disabled={!canManage}>
                      {t("serviceDetailsPage.actions.addException")}
                    </button>
                  </div>
                  {schedule?.exceptions?.length ? (
                    <ul className="list">
                      {schedule.exceptions.map((item) => (
                        <li key={item.id} className="list-item">
                          <div>
                            <strong>{item.date}</strong>{" "}
                            {item.is_closed
                              ? t("serviceDetailsPage.schedule.closed")
                              : t("serviceDetailsPage.schedule.exceptionSummary", {
                                  from: item.time_from ?? "—",
                                  to: item.time_to ?? "—",
                                  value: item.capacity_override ?? t("serviceDetailsPage.schedule.byRule"),
                                })}
                          </div>
                          {canManage ? (
                            <button type="button" className="danger" onClick={() => handleRemoveException(item.id)}>
                              {t("actions.delete")}
                            </button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState
                      title={t("serviceDetailsPage.empty.exceptionsTitle")}
                      description={t("serviceDetailsPage.empty.exceptionsDescription")}
                    />
                  )}
                </div>
              </>
            ) : (
              <EmptyState
                title={t("serviceDetailsPage.empty.selectLocationTitle")}
                description={t("serviceDetailsPage.empty.selectLocationDescription")}
              />
            )}
          </div>
        ) : null}
        {tab === "preview" ? (
          <div className="stack">
            <div className="stack-inline">
              <label className="field">
                <span>{t("serviceDetailsPage.fields.period")}</span>
                <div className="stack-inline">
                  <input
                    type="date"
                    value={availabilityRange.from}
                    onChange={(event) => setAvailabilityRange((prev) => ({ ...prev, from: event.target.value }))}
                  />
                  <input
                    type="date"
                    value={availabilityRange.to}
                    onChange={(event) => setAvailabilityRange((prev) => ({ ...prev, to: event.target.value }))}
                  />
                </div>
              </label>
            </div>
            {availabilityLoading ? (
              <LoadingState label={t("serviceDetailsPage.tabs.preview")} />
            ) : availabilityError ? (
              <ErrorState
                title={t("serviceDetailsPage.tabs.preview")}
                description={availabilityError}
                action={
                  <button type="button" className="secondary" onClick={() => setRetryKey((value) => value + 1)}>
                    {t("actions.refresh")}
                  </button>
                }
              />
            ) : availability.length === 0 ? (
              <EmptyState
                title={t("serviceDetailsPage.empty.slotsTitle")}
                description={t("serviceDetailsPage.empty.slotsDescription")}
              />
            ) : (
              <ul className="list">
                {availability.map((slot) => (
                  <li key={`${slot.service_location_id}-${slot.date}-${slot.time_from}`} className="list-item">
                    <div>
                      <strong>{slot.date}</strong> {slot.time_from}–{slot.time_to}
                      <div className="muted">{t("serviceDetailsPage.schedule.slotsValue", { value: slot.capacity })}</div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}
