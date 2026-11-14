import { CONFIG } from './config.js';
import { mockRequest } from './mock-data.js';
export { metrics } from './mock-data.js';
let settings={...CONFIG};
export const getSettings=()=>({...settings});
export function configure({useMock,baseUrl}) {
  const url=new URL(baseUrl);if(!['http:','https:'].includes(url.protocol))throw new Error('Введите HTTP или HTTPS URL');
  settings={...settings,USE_MOCK_DATA:!!useMock,API_BASE_URL:url.href.replace(/\/$/,'')};
}
export const uid=()=>globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`;
const routes={products:['GET','/products'],search:['GET','/products/search'],discounts:['GET','/discounts'],ads:['GET','/ads/recommendations'],impression:['POST','/ads/impression'],click:['POST','/ads/click'],order:['POST','/orders/demo'],overview:['GET','/analytics/overview'],campaigns:['GET','/analytics/campaigns'],rpi:['GET','/analytics/rpi'],recommendations:['GET','/recommendations'],update:['PATCH','/products/'],reset:['POST','/demo/reset']};
const arrays=new Set(['products','search','discounts','ads','campaigns','recommendations']);
function validate(action,data){
  if(arrays.has(action)&&!Array.isArray(data))throw new Error('API: ожидался массив data');
  if(!arrays.has(action)&&(!data||typeof data!=='object'||Array.isArray(data)))throw new Error('API: ожидался объект data');
  const required={products:['product_id','name','price','current_price','category','in_stock','discount'],search:['product_id','name','price','current_price','category','in_stock','discount'],ads:['product_id','campaign_id','name','score','relevance','discount_score','performance','current_price','explanation'],campaigns:['campaign_id','name','impressions','clicks','confirmed_purchases','spend','revenue','rpi'],discounts:['product_id','percent','active','start_at','end_at'],recommendations:['id','title','status','text'],overview:['impressions','clicks','confirmed_purchases','spend','revenue','ctr','cvr','cpa','roas','rpi','daily','budget'],rpi:['current','baseline','change_percent'],impression:['impression_id'],click:['click_id'],order:['order_id','status','is_demo'],update:['product_id'],reset:['ok']}[action]||[];
  for(const item of arrays.has(action)?data:[data])if(!item||required.some(k=>!(k in item)))throw new Error(`API: неполная модель ${action}`);
  const finite=(value,min=0,max=Infinity)=>typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max;
  const analytics=a=>{
    if(!a||!['impressions','clicks','confirmed_purchases','cancelled_orders','relevant_impressions','available_impressions','spend','revenue','budget','active_campaigns','available_products','active_discounts'].every(k=>finite(a[k])))return false;
    if(!['ctr','cvr','rpi'].every(k=>finite(a[k],0,100))||!['rr','ar'].every(k=>finite(a[k],0,1)))return false;
    if(!['cpc','cpa','roas'].every(k=>a[k]===null||finite(a[k])))return false;
    return a.confirmed_purchases<=a.clicks&&a.clicks<=a.impressions&&a.relevant_impressions<=a.impressions&&a.available_impressions<=a.impressions&&Array.isArray(a.daily)&&a.daily.every(d=>typeof d.date==='string'&&['impressions','clicks','confirmed_purchases','spend','revenue'].every(k=>finite(d[k])));
  };
  if(action==='overview'&&!analytics(data)||action==='campaigns'&&!data.every(analytics)||action==='rpi'&&(!analytics(data.current)||!analytics(data.baseline)||(data.change_percent!==null&&!Number.isFinite(data.change_percent))))throw new Error('API: некорректная структура или диапазон аналитики');
  if(['products','search','ads'].includes(action)&&!data.every(p=>typeof p.product_id==='string'&&typeof p.name==='string'&&finite(p.current_price)&&typeof p.in_stock==='boolean'))throw new Error('API: некорректная модель товара');
  if(action==='ads'&&!data.every(p=>['score','relevance','discount_score','performance'].every(k=>finite(p[k],0,1))))throw new Error('API: оценки рекламы должны быть в диапазоне 0–1');
  return data;
}
async function request(action,args={}){
  if(settings.USE_MOCK_DATA){await new Promise(r=>setTimeout(r,80));return mockRequest(action,args);}
  const [method,path]=routes[action], url=new URL(settings.API_BASE_URL+path+(action==='update'?encodeURIComponent(args.product_id):''));
  if(method==='GET')for(const [k,v]of Object.entries(args))if(v!==''&&v!==undefined)url.searchParams.set(k,String(v));
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),settings.REQUEST_TIMEOUT_MS);
  try{
    const response=await fetch(url,{method,signal:controller.signal,headers:{Accept:'application/json',...(method!=='GET'?{'Content-Type':'application/json'}:{})},...(method!=='GET'?{body:JSON.stringify(args)}:{})});
    let payload;try{payload=await response.json();}catch{throw new Error(`API вернул не JSON (HTTP ${response.status})`);}
    if(!response.ok)throw new Error(payload.error?.message||`HTTP ${response.status}`);
    if(!payload||!('data' in payload))throw new Error('API: отсутствует поле data');
    return validate(action,payload.data);
  }catch(e){if(e.name==='AbortError')throw new Error('Сервер не ответил за 12 секунд');throw e;}
  finally{clearTimeout(timer);}
}
export const api={
  getProducts:()=>request('products'),searchProducts:args=>request('search',args),getDiscounts:()=>request('discounts'),getAds:args=>request('ads',args),
  sendImpression:body=>request('impression',body),sendClick:body=>request('click',body),createDemoOrder:body=>request('order',body),
  getOverview:args=>request('overview',args),getCampaigns:args=>request('campaigns',args),getRpi:args=>request('rpi',args),getRecommendations:args=>request('recommendations',args),
  updateProduct:body=>request('update',body),resetDemo:()=>{if(!settings.USE_MOCK_DATA)throw new Error('Сброс доступен только в локальном DEMO');return request('reset');}
};
