import { request } from "./http";
import type {
  PartnerLegalDetails,
  PartnerLegalDetailsUpdate,
  PartnerLegalProfile,
  PartnerLegalProfileResponse,
  PartnerLegalProfileUpdate,
} from "../types/partnerLegal";

export const fetchPartnerLegalProfile = (token: string) =>
  request<PartnerLegalProfileResponse>("/partner/legal/profile", {}, token, "core_root");

export const upsertPartnerLegalProfile = (token: string, payload: PartnerLegalProfileUpdate) =>
  request<PartnerLegalProfile>(
    "/partner/legal/profile",
    { method: "PUT", body: JSON.stringify(payload) },
    token,
    "core_root",
  );

export const upsertPartnerLegalDetails = (token: string, payload: PartnerLegalDetailsUpdate) =>
  request<PartnerLegalDetails>(
    "/partner/legal/details",
    { method: "PUT", body: JSON.stringify(payload) },
    token,
    "core_root",
  );
