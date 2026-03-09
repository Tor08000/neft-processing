import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createOrg } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";
import { CustomerType, getPlanByCode, getPlansByAudience } from "@shared/subscriptions/catalog";

export type ConnectProfileField = "fullName"|"legalName"|"phone"|"email"|"inn"|"kpp"|"ogrn"|"ogrnip"|"address"|"contact";
type ConnectProfileValues = Record<ConnectProfileField, string>;
type ConnectProfileErrors = Partial<Record<ConnectProfileField, string>>;

const CLIENT_PLANS = getPlansByAudience("CLIENT");

export function ConnectHomePage() {
  const { state, nextRoute } = useClientJourney();
  return <div className="stack card neft-card"><h1>Подключение клиента</h1><p>Текущий этап: {state}</p><p className="muted">Для полного доступа завершите подключение компании и подписку.</p><Link className="neft-button neft-btn-primary" to={nextRoute === "/connect" ? "/connect/plan" : nextRoute}>Продолжить подключение</Link></div>;
}

export function ConnectPlanPage() {
  const { updateDraft, draft } = useClientJourney();
  const navigate = useNavigate();
  return <div className="stack card neft-card"><h1>Выбор тарифа</h1>{CLIENT_PLANS.map((plan)=><div key={plan.code} className="card neft-card stack"><h2>{plan.title} {plan.badge ? <span className="muted">· {plan.badge}</span> : null}</h2><div>{plan.monthlyPrice == null ? "Индивидуально" : `₽${plan.monthlyPrice} / мес`}</div><div className="muted">{plan.yearlyDiscountText ?? ""}</div><div>{plan.description}</div><ul>{plan.bullets.map((item)=><li key={item}>{item}</li>)}</ul><div className="muted">Лимиты: users {plan.limits.users ?? "∞"}, cards {plan.limits.cards ?? "—"}</div><button className={`neft-button ${draft.selectedPlan===plan.code?"neft-btn-secondary":"neft-btn-primary"}`} onClick={()=>{updateDraft({ selectedPlan: plan.code, subscriptionState: plan.isTrial ? "TRIAL_PENDING" : "NONE" });navigate("/connect/type");}}>Выбрать {plan.shortTitle}</button></div>)}</div>;
}

export function ConnectTypePage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const types: Array<{ code: CustomerType; label: string }> = [
    { code: "INDIVIDUAL", label: "Физическое лицо" },
    { code: "SOLE_PROPRIETOR", label: "Индивидуальный предприниматель" },
    { code: "LEGAL_ENTITY", label: "Юридическое лицо" },
  ];
  return <div className="stack card neft-card"><h1>Тип клиента</h1>{types.map((type)=><button key={type.code} className="neft-button neft-btn-secondary" onClick={()=>{updateDraft({ customerType: type.code, profileCompleted: false });navigate("/connect/profile");}}>{type.label}</button>)}</div>;
}

export function getProfileFields(customerType: CustomerType | null | undefined): ConnectProfileField[] { if (customerType === "INDIVIDUAL") return ["fullName","phone","email","address"]; if (customerType === "SOLE_PROPRIETOR") return ["fullName","inn","ogrnip","address","contact"]; return ["legalName","inn","kpp","ogrn","address","contact"]; }

export function ConnectProfilePage() { const { user } = useAuth(); const { draft, updateDraft } = useClientJourney(); const { refresh } = useClient(); const navigate = useNavigate(); const [values,setValues]=useState<ConnectProfileValues>({fullName:"",legalName:"",phone:"",email:user?.email??"",address:"",inn:"",kpp:"",ogrn:"",ogrnip:"",contact:""}); const [errors,setErrors]=useState<ConnectProfileErrors>({}); const [submitError,setSubmitError]=useState<string|null>(null); const requiredFields=useMemo(()=>getProfileFields(draft.customerType),[draft.customerType]); const setField=(f:ConnectProfileField,v:string)=>{setValues((p)=>({...p,[f]:v}));setErrors((p)=>({...p,[f]:""}));}; const validate=()=>{const e:ConnectProfileErrors={}; requiredFields.forEach((f)=>{if(!values[f]?.trim()) e[f]="Обязательное поле";}); setErrors(e); return Object.keys(e).length===0;};
  const onSubmit=async(e:FormEvent)=>{e.preventDefault(); setSubmitError(null); if(!validate()) return; if(!draft.customerType){setSubmitError("Сначала выберите тип клиента"); return;} try { if(user){ const orgType=draft.customerType==="LEGAL_ENTITY"?"LEGAL":draft.customerType==="SOLE_PROPRIETOR"?"IP":"INDIVIDUAL"; const name=draft.customerType==="LEGAL_ENTITY"?values.legalName:values.fullName; await createOrg(user,{org_type:orgType,name,inn:values.inn||"-",kpp:values.kpp||null,ogrn:values.ogrn||values.ogrnip||null,address:values.address||null}); await refresh(); } updateDraft({profileCompleted:true,documentsGenerated:false,documentsViewed:false}); navigate("/connect/documents"); } catch { setSubmitError("Не удалось сохранить профиль. Проверьте поля и попробуйте снова."); }};
  if(!draft.customerType){return <div className="stack card neft-card"><h1>Профиль клиента</h1><p>Сначала выберите тип клиента.</p><Link to="/connect/type" className="neft-button neft-btn-primary">Выбрать тип</Link></div>;}
  return <form onSubmit={onSubmit} className="stack card neft-card"><h1>Профиль клиента</h1>{submitError?<div role="alert">{submitError}</div>:null}{requiredFields.includes("fullName")?<input className="neft-input" value={values.fullName} onChange={(e)=>setField("fullName",e.target.value)} placeholder="ФИО" aria-invalid={Boolean(errors.fullName)}/>:null}{requiredFields.includes("legalName")?<input className="neft-input" value={values.legalName} onChange={(e)=>setField("legalName",e.target.value)} placeholder="Полное наименование" aria-invalid={Boolean(errors.legalName)}/>:null}{requiredFields.includes("phone")?<input className="neft-input" value={values.phone} onChange={(e)=>setField("phone",e.target.value)} placeholder="Телефон" aria-invalid={Boolean(errors.phone)}/>:null}{requiredFields.includes("email")?<input className="neft-input" value={values.email} onChange={(e)=>setField("email",e.target.value)} placeholder="Email" aria-invalid={Boolean(errors.email)}/>:null}{requiredFields.includes("inn")?<input className="neft-input" value={values.inn} onChange={(e)=>setField("inn",e.target.value)} placeholder="ИНН" aria-invalid={Boolean(errors.inn)}/>:null}{requiredFields.includes("kpp")?<input className="neft-input" value={values.kpp} onChange={(e)=>setField("kpp",e.target.value)} placeholder="КПП" aria-invalid={Boolean(errors.kpp)}/>:null}{requiredFields.includes("ogrn")?<input className="neft-input" value={values.ogrn} onChange={(e)=>setField("ogrn",e.target.value)} placeholder="ОГРН" aria-invalid={Boolean(errors.ogrn)}/>:null}{requiredFields.includes("ogrnip")?<input className="neft-input" value={values.ogrnip} onChange={(e)=>setField("ogrnip",e.target.value)} placeholder="ОГРНИП" aria-invalid={Boolean(errors.ogrnip)}/>:null}{requiredFields.includes("address")?<input className="neft-input" value={values.address} onChange={(e)=>setField("address",e.target.value)} placeholder="Адрес" aria-invalid={Boolean(errors.address)}/>:null}{requiredFields.includes("contact")?<input className="neft-input" value={values.contact} onChange={(e)=>setField("contact",e.target.value)} placeholder="Контактное лицо" aria-invalid={Boolean(errors.contact)}/>:null}{Object.values(errors).filter(Boolean).length>0?<div role="alert">Заполните обязательные поля.</div>:null}<button type="submit" className="neft-button neft-btn-primary">Продолжить</button></form>;
}

export function ConnectDocumentsPage() {
  const { draft, updateDraft } = useClientJourney();
  const plan = getPlanByCode(draft.selectedPlan);
  const navigate = useNavigate();
  return <div className="stack card neft-card"><h1>Документы</h1><p>План: {plan?.title ?? draft.selectedPlan ?? "не выбран"}</p><p>Тип клиента: {draft.customerType ?? "не выбран"}</p><button className="neft-button neft-btn-secondary" onClick={()=>updateDraft({documentsGenerated:true})}>Сгенерировать документы</button><button className="neft-button neft-btn-primary" onClick={()=>{updateDraft({documentsGenerated:true,documentsViewed:true});navigate("/connect/sign");}}>Я ознакомился, перейти к подписанию</button></div>;
}

export function ConnectSignPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);
  return <div className="stack card neft-card"><h1>Подписание</h1><p>Подписка: {plan?.title ?? draft.selectedPlan}</p><p className="muted">Интеграция e-sign пока в режиме stub.</p><button className="neft-button neft-btn-primary" onClick={()=>{const nextState = draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "TRIAL_ACTIVE" : "PAYMENT_PENDING"; updateDraft({documentsSigned:true,subscriptionState: nextState}); navigate(draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "/dashboard" : "/connect/payment");}}>Подписать и продолжить</button></div>;
}

export function ConnectPaymentPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);
  return <div className="stack card neft-card"><h1>Оплата подписки</h1><p>Тариф: {plan?.title ?? draft.selectedPlan ?? "не выбран"}</p><p>К оплате: {plan?.monthlyPrice == null ? "по договору" : `₽${plan.monthlyPrice}`}</p><p>Статус: {draft.subscriptionState ?? "NONE"}</p><button className="neft-button neft-btn-secondary" onClick={()=>updateDraft({ subscriptionState: "PAYMENT_FAILED" })}>Эмулировать ошибку оплаты</button><button className="neft-button neft-btn-primary" onClick={()=>{updateDraft({subscriptionState:"ACTIVE"});navigate("/dashboard");}}>Pay subscription</button></div>;
}
