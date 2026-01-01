import React, { useEffect, useState } from "react";

import {
  createAchievement,
  createBonus,
  createStreak,
  listAchievements,
  listBonuses,
  listStreaks,
  updateAchievement,
  updateBonus,
  updateStreak,
} from "../../api/subscriptions";
import { useAuth } from "../../auth/AuthContext";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { Achievement, Bonus, Streak } from "../../types/subscriptions";

const formatPlanCodes = (codes?: string[] | null) => (codes?.length ? codes.join(", ") : "");
const parsePlanCodes = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);

export const SubscriptionGamificationPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [streaks, setStreaks] = useState<Streak[]>([]);
  const [bonuses, setBonuses] = useState<Bonus[]>([]);
  const [draftAchievement, setDraftAchievement] = useState({
    code: "",
    title: "",
    description: "",
    is_active: true,
    is_hidden: false,
    module_code: "",
    plan_codes: "",
  });
  const [draftStreak, setDraftStreak] = useState({
    code: "",
    title: "",
    description: "",
    is_active: true,
    module_code: "",
    plan_codes: "",
    condition: "{}",
  });
  const [draftBonus, setDraftBonus] = useState({
    code: "",
    title: "",
    description: "",
    is_active: true,
    plan_codes: "",
    reward: "{}",
  });

  const loadData = () => {
    if (!accessToken) return;
    Promise.all([listAchievements(accessToken), listStreaks(accessToken), listBonuses(accessToken)])
      .then(([achievementResponse, streakResponse, bonusResponse]) => {
        setAchievements(achievementResponse);
        setStreaks(streakResponse);
        setBonuses(bonusResponse);
      })
      .catch((error: unknown) => showToast("error", String(error)));
  };

  useEffect(() => {
    loadData();
  }, [accessToken]);

  const handleCreateAchievement = async () => {
    if (!accessToken) return;
    try {
      const created = await createAchievement(accessToken, {
        code: draftAchievement.code,
        title: draftAchievement.title,
        description: draftAchievement.description || null,
        is_active: draftAchievement.is_active,
        is_hidden: draftAchievement.is_hidden,
        module_code: draftAchievement.module_code || null,
        plan_codes: parsePlanCodes(draftAchievement.plan_codes),
      });
      setAchievements((prev) => [created, ...prev]);
      setDraftAchievement({ code: "", title: "", description: "", is_active: true, is_hidden: false, module_code: "", plan_codes: "" });
      showToast("success", "Achievement created");
    } catch (error: unknown) {
      showToast("error", String(error));
    }
  };

  const handleCreateStreak = async () => {
    if (!accessToken) return;
    try {
      const created = await createStreak(accessToken, {
        code: draftStreak.code,
        title: draftStreak.title,
        description: draftStreak.description || null,
        is_active: draftStreak.is_active,
        module_code: draftStreak.module_code || null,
        plan_codes: parsePlanCodes(draftStreak.plan_codes),
        condition: draftStreak.condition ? JSON.parse(draftStreak.condition) : null,
      });
      setStreaks((prev) => [created, ...prev]);
      setDraftStreak({ code: "", title: "", description: "", is_active: true, module_code: "", plan_codes: "", condition: "{}" });
      showToast("success", "Streak created");
    } catch (error: unknown) {
      showToast("error", "Invalid streak payload");
    }
  };

  const handleCreateBonus = async () => {
    if (!accessToken) return;
    try {
      const created = await createBonus(accessToken, {
        code: draftBonus.code,
        title: draftBonus.title,
        description: draftBonus.description || null,
        is_active: draftBonus.is_active,
        plan_codes: parsePlanCodes(draftBonus.plan_codes),
        reward: draftBonus.reward ? JSON.parse(draftBonus.reward) : null,
      });
      setBonuses((prev) => [created, ...prev]);
      setDraftBonus({ code: "", title: "", description: "", is_active: true, plan_codes: "", reward: "{}" });
      showToast("success", "Bonus created");
    } catch (error: unknown) {
      showToast("error", "Invalid bonus payload");
    }
  };

  const toggleAchievement = async (item: Achievement) => {
    if (!accessToken) return;
    const updated = await updateAchievement(accessToken, item.id, { is_active: !item.is_active });
    setAchievements((prev) => prev.map((entry) => (entry.id === updated.id ? updated : entry)));
  };

  const toggleStreak = async (item: Streak) => {
    if (!accessToken) return;
    const updated = await updateStreak(accessToken, item.id, { is_active: !item.is_active });
    setStreaks((prev) => prev.map((entry) => (entry.id === updated.id ? updated : entry)));
  };

  const toggleBonus = async (item: Bonus) => {
    if (!accessToken) return;
    const updated = await updateBonus(accessToken, item.id, { is_active: !item.is_active });
    setBonuses((prev) => prev.map((entry) => (entry.id === updated.id ? updated : entry)));
  };

  return (
    <div>
      <Toast toast={toast} />
      <h1>Subscriptions · Gamification</h1>

      <section className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Achievements</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {achievements.map((item) => (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{item.code}</strong> · {item.title}
                <div style={{ color: "#64748b" }}>Plans: {formatPlanCodes(item.plan_codes) || "all"}</div>
              </div>
              <button className="neft-btn-secondary" type="button" onClick={() => toggleAchievement(item)}>
                {item.is_active ? "Disable" : "Enable"}
              </button>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <h4>Create achievement</h4>
          <input className="neft-input" placeholder="Code" value={draftAchievement.code} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, code: event.target.value }))} />
          <input className="neft-input" placeholder="Title" value={draftAchievement.title} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, title: event.target.value }))} />
          <textarea className="neft-input" placeholder="Description" value={draftAchievement.description} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, description: event.target.value }))} />
          <input className="neft-input" placeholder="Module code" value={draftAchievement.module_code} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, module_code: event.target.value }))} />
          <input className="neft-input" placeholder="Plan codes (comma)" value={draftAchievement.plan_codes} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, plan_codes: event.target.value }))} />
          <div style={{ display: "flex", gap: 12 }}>
            <label>
              Active
              <select className="neft-input" value={draftAchievement.is_active ? "true" : "false"} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, is_active: event.target.value === "true" }))}>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </label>
            <label>
              Hidden
              <select className="neft-input" value={draftAchievement.is_hidden ? "true" : "false"} onChange={(event) => setDraftAchievement((prev) => ({ ...prev, is_hidden: event.target.value === "true" }))}>
                <option value="false">Visible</option>
                <option value="true">Hidden</option>
              </select>
            </label>
          </div>
          <button className="neft-btn" type="button" onClick={handleCreateAchievement}>Create</button>
        </div>
      </section>

      <section className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Streaks</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {streaks.map((item) => (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{item.code}</strong> · {item.title}
                <div style={{ color: "#64748b" }}>Plans: {formatPlanCodes(item.plan_codes) || "all"}</div>
              </div>
              <button className="neft-btn-secondary" type="button" onClick={() => toggleStreak(item)}>
                {item.is_active ? "Disable" : "Enable"}
              </button>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <h4>Create streak</h4>
          <input className="neft-input" placeholder="Code" value={draftStreak.code} onChange={(event) => setDraftStreak((prev) => ({ ...prev, code: event.target.value }))} />
          <input className="neft-input" placeholder="Title" value={draftStreak.title} onChange={(event) => setDraftStreak((prev) => ({ ...prev, title: event.target.value }))} />
          <textarea className="neft-input" placeholder="Description" value={draftStreak.description} onChange={(event) => setDraftStreak((prev) => ({ ...prev, description: event.target.value }))} />
          <input className="neft-input" placeholder="Module code" value={draftStreak.module_code} onChange={(event) => setDraftStreak((prev) => ({ ...prev, module_code: event.target.value }))} />
          <input className="neft-input" placeholder="Plan codes (comma)" value={draftStreak.plan_codes} onChange={(event) => setDraftStreak((prev) => ({ ...prev, plan_codes: event.target.value }))} />
          <textarea className="neft-input" placeholder="Condition (JSON)" value={draftStreak.condition} onChange={(event) => setDraftStreak((prev) => ({ ...prev, condition: event.target.value }))} />
          <label>
            Active
            <select className="neft-input" value={draftStreak.is_active ? "true" : "false"} onChange={(event) => setDraftStreak((prev) => ({ ...prev, is_active: event.target.value === "true" }))}>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
          <button className="neft-btn" type="button" onClick={handleCreateStreak}>Create</button>
        </div>
      </section>

      <section className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Bonuses</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {bonuses.map((item) => (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{item.code}</strong> · {item.title}
                <div style={{ color: "#64748b" }}>Plans: {formatPlanCodes(item.plan_codes) || "all"}</div>
              </div>
              <button className="neft-btn-secondary" type="button" onClick={() => toggleBonus(item)}>
                {item.is_active ? "Disable" : "Enable"}
              </button>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <h4>Create bonus</h4>
          <input className="neft-input" placeholder="Code" value={draftBonus.code} onChange={(event) => setDraftBonus((prev) => ({ ...prev, code: event.target.value }))} />
          <input className="neft-input" placeholder="Title" value={draftBonus.title} onChange={(event) => setDraftBonus((prev) => ({ ...prev, title: event.target.value }))} />
          <textarea className="neft-input" placeholder="Description" value={draftBonus.description} onChange={(event) => setDraftBonus((prev) => ({ ...prev, description: event.target.value }))} />
          <input className="neft-input" placeholder="Plan codes (comma)" value={draftBonus.plan_codes} onChange={(event) => setDraftBonus((prev) => ({ ...prev, plan_codes: event.target.value }))} />
          <textarea className="neft-input" placeholder="Reward (JSON)" value={draftBonus.reward} onChange={(event) => setDraftBonus((prev) => ({ ...prev, reward: event.target.value }))} />
          <label>
            Active
            <select className="neft-input" value={draftBonus.is_active ? "true" : "false"} onChange={(event) => setDraftBonus((prev) => ({ ...prev, is_active: event.target.value === "true" }))}>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
          <button className="neft-btn" type="button" onClick={handleCreateBonus}>Create</button>
        </div>
      </section>
    </div>
  );
};

export default SubscriptionGamificationPage;
