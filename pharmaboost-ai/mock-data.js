// Только локальный симулятор. В API-режиме ранжирование и события принадлежат серверу.
export const DEMO_DATE = '2026-11-14T12:00:00+05:00';
const clone = value => structuredClone(value);
const products = [
  { product_id:'p1', pharmacy_id:'ph1', name:'Шампунь Daily Balance', brand:'BOTANICA', category:'Волосы', keywords:['шампунь','шамп','shampoo','волосы','уход за волосами'], price:4800, in_stock:true, ad_allowed:true, shape:'bottle', color:'mint', volume:'250 мл' },
  { product_id:'p2', pharmacy_id:'ph1', name:'Шампунь Gentle Care', brand:'PURE LAB', category:'Волосы', keywords:['шампунь','шамп','shampoo','волосы','мягкий'], price:5600, in_stock:true, ad_allowed:true, shape:'bottle', color:'blue', volume:'300 мл' },
  { product_id:'p3', pharmacy_id:'ph2', name:'Шампунь Fresh Ritual', brand:'NATURALIST', category:'Волосы', keywords:['шампунь','шамп','shampoo','волосы','свежесть'], price:3900, in_stock:false, ad_allowed:true, shape:'bottle', color:'peach', volume:'250 мл' },
  { product_id:'p4', pharmacy_id:'ph2', name:'Солнцезащитный крем SPF 50', brand:'SUN THEORY', category:'Защита от солнца', keywords:['солнцезащитный крем','солнце','spf','санскрин','защита от солнца'], price:7200, in_stock:true, ad_allowed:true, shape:'tube', color:'yellow', volume:'50 мл' },
  { product_id:'p5', pharmacy_id:'ph1', name:'Крем для рук Soft Touch', brand:'BOTANICA', category:'Уход за кожей', keywords:['крем для рук','руки','увлажнение','кожа','уход'], price:2400, in_stock:true, ad_allowed:true, shape:'tube', color:'peach', volume:'75 мл' },
  { product_id:'p6', pharmacy_id:'ph2', name:'Зубная паста Everyday', brand:'PURE LAB', category:'Гигиена', keywords:['зубная паста','зубы','паста','гигиена','toothpaste'], price:1800, in_stock:true, ad_allowed:true, shape:'tube', color:'blue', volume:'100 мл' },
  { product_id:'p7', pharmacy_id:'ph1', name:'Сыворотка с витамином C', brand:'BOTANICA', category:'Уход за кожей', keywords:['витамин c','витамин с','vitamin c','сыворотка','кожа'], price:6400, in_stock:true, ad_allowed:true, shape:'bottle', color:'yellow', volume:'30 мл' },
  { product_id:'p8', pharmacy_id:'ph2', name:'Расчёска для волос', brand:'DAILY', category:'Волосы', keywords:['расческа','волосы','аксессуары'], price:1500, in_stock:true, ad_allowed:false, shape:'box', color:'mint', volume:'1 шт.' }
];
function initialState() {
  const campaigns = products.slice(0,7).map((p,i)=>({campaign_id:`c${i+1}`,product_id:p.product_id,name:p.name,status:'active',budget:80000+i*12000}));
  const discounts = products.map((p,i)=>({product_id:p.product_id,percent:[10,5,25,15,20,0,10,0][i],active:i!==1,start_at:'2026-11-01T00:00:00+05:00',end_at:i===6?'2026-11-10T23:59:59+05:00':'2026-12-01T00:00:00+05:00'}));
  const daily = [];
  for (let c=0;c<7;c++) for (let d=0;d<7;d++) {
    const impressions=2600+c*280+d*110, clicks=100+c*9+d*5, purchases=3+(c%3)+(d%2)+(c===0?1:0);
    for (const scenario of ['before','after']) {
      const after=scenario==='after', confirmed_purchases=purchases+(after?2:0);
      daily.push({campaign_id:`c${c+1}`,date:`2026-11-${String(8+d).padStart(2,'0')}`,scenario,impressions,clicks:clicks+(after?12:0),confirmed_purchases,cancelled_orders:1,relevant_impressions:Math.floor(impressions*(after?.92:c===2?.42:c===5?.81:.72)),available_impressions:Math.floor(impressions*(after?.97:.88)),spend:2600+c*180+d*70,revenue:confirmed_purchases*products[c].price});
    }
  }
  return {products:clone(products),pharmacies:[{pharmacy_id:'ph1',name:'Аптека Green'},{pharmacy_id:'ph2',name:'Аптека City'}],campaigns,discounts,daily,impressions:{},clicks:{},orders:{}};
}
let db=initialState();
export function resetMock(){ db=initialState(); return {ok:true}; }
export function metrics(a) {
  const div=(n,d)=>d?n/d:0;
  const cvr=div(a.confirmed_purchases,a.clicks), rr=div(a.relevant_impressions,a.impressions), ar=div(a.available_impressions,a.impressions);
  return {ctr:100*div(a.clicks,a.impressions),cpc:a.clicks?a.spend/a.clicks:null,cvr:100*cvr,cpa:a.confirmed_purchases?a.spend/a.confirmed_purchases:null,roas:a.spend?a.revenue/a.spend:null,rpi:100*cvr*rr*ar,rr,ar};
}
const norm=s=>String(s).toLowerCase().replace(/ё/g,'е').replace(/с(?=\s|$)/g,'c').trim();
export function relevance(p,q) {
  q=norm(q); if(!q) return .65;
  const name=norm(p.name), category=norm(p.category), words=p.keywords.map(norm);
  if(name.includes(q)) return 1;
  if(words.some(w=>w===q)) return .95;
  if(category.includes(q)) return .85;
  if(words.some(w=>w.includes(q)||q.includes(w))) return .8;
  const tokens=q.split(/\s+/).filter(w=>w.length>2);
  const hits=tokens.filter(w=>name.includes(w)||words.some(k=>k.includes(w))).length;
  return tokens.length&&hits===tokens.length?.7:0;
}
export function validDiscount(d,now=DEMO_DATE){return !!d&&d.percent>0&&d.active&&Date.parse(d.start_at)<=Date.parse(now)&&Date.parse(d.end_at)>Date.parse(now);}
function enriched(p){ const discount=db.discounts.find(d=>d.product_id===p.product_id); return {...p,discount:clone(discount),effective_discount:validDiscount(discount)?discount.percent:0,current_price:Math.round(p.price*(1-(validDiscount(discount)?discount.percent:0)/100)),pharmacy:db.pharmacies.find(x=>x.pharmacy_id===p.pharmacy_id).name}; }
const fields=['impressions','clicks','confirmed_purchases','cancelled_orders','relevant_impressions','available_impressions','spend','revenue'];
function sum(rows){return rows.reduce((a,r)=>{for(const k of fields)a[k]+=r[k]||0;return a;},Object.fromEntries(fields.map(k=>[k,0])));}
function rowsFor(campaign_id,scenario){return db.daily.filter(r=>r.scenario===scenario&&(!campaign_id||r.campaign_id===campaign_id));}
function overview({campaign_id='',scenario='after'}={}){
  const rows=rowsFor(campaign_id,scenario), totals=sum(rows);
  return {...totals,...metrics(totals),scenario,budget:db.campaigns.filter(c=>!campaign_id||c.campaign_id===campaign_id).reduce((a,c)=>a+c.budget,0),daily:[...new Set(rows.map(r=>r.date))].map(date=>({date,...sum(rows.filter(r=>r.date===date))})),active_campaigns:db.campaigns.filter(c=>c.status==='active'&&(!campaign_id||c.campaign_id===campaign_id)).length,available_products:db.products.filter(p=>p.in_stock&&(!campaign_id||db.campaigns.find(c=>c.campaign_id===campaign_id)?.product_id===p.product_id)).length,active_discounts:db.discounts.filter(d=>validDiscount(d)&&(!campaign_id||db.campaigns.find(c=>c.campaign_id===campaign_id)?.product_id===d.product_id)).length};
}
function ranked({q='',campaign_id='',smart=true}={}){
  return db.products.filter(p=>p.in_stock&&p.ad_allowed).map(p=>{
    const campaign=db.campaigns.find(c=>c.product_id===p.product_id&&c.status==='active'&&(!campaign_id||c.campaign_id===campaign_id));
    const r=relevance(p,q); if(!campaign||!r)return null;
    const product=enriched(p), historical=overview({campaign_id:campaign.campaign_id,scenario:'before'});
    const performance=Math.min(historical.cvr/10,1), discount=product.effective_discount/100;
    return {...product,campaign_id:campaign.campaign_id,relevance:r,discount_score:discount,performance,score:.5*r+(smart?.2*discount:0)+.3*performance,explanation:`Товар ${q?`соответствует запросу «${q}»`:'входит в текущую подборку'}, есть в наличии и участвует в активной кампании. Актуальная скидка: ${product.effective_discount}%.`};
  }).filter(Boolean).sort((a,b)=>b.score-a.score||a.product_id.localeCompare(b.product_id));
}
function recommendations(args){
  const output=[];
  for(const c of db.campaigns.filter(c=>!args.campaign_id||c.campaign_id===args.campaign_id)){
    const p=enriched(db.products.find(p=>p.product_id===c.product_id)), a=overview({campaign_id:c.campaign_id,scenario:'before'});
    if(!p.in_stock)output.push({id:`stock-${p.product_id}`,title:'Товар закончился',status:'Требует внимания',text:`${p.name}: нет в наличии. Приостановите показы. Демонстрационное ранжирование уже исключило товар.`,product_id:p.product_id});
    if(a.rr<.75)output.push({id:`rel-${p.product_id}`,title:'Повысить релевантность',status:'Рекомендуется',text:`${p.name}: ${(a.rr*100).toFixed(0)}% релевантных показов в контрольном периоде. Уточните подбор по запросам.`,product_id:p.product_id});
    if(a.cvr<3.5)output.push({id:`cvr-${p.product_id}`,title:'Проверить конверсию',status:'Требует внимания',text:`${p.name}: CVR ${a.cvr.toFixed(2)}% ниже демонстрационного ориентира 3,5%. Проверьте цену, карточку и наличие.`,product_id:p.product_id});
    if(p.in_stock&&p.effective_discount>=15)output.push({id:`sale-${p.product_id}`,title:'Протестировать долю показов',status:'Рекомендуется',text:`${p.name}: актуальная скидка ${p.effective_discount}%. Увеличение доли стоит тестировать только для релевантных запросов и в рамках бюджета.`,product_id:p.product_id});
    if(p.in_stock&&a.rr>=.75)output.push({id:`ok-${p.product_id}`,title:'Проверки пройдены',status:'Оптимизировано',text:`${p.name}: товар доступен, релевантность выше демонстрационного ориентира 75%. Продолжайте контроль.`,product_id:p.product_id});
  } return output;
}
function fail(message){throw new Error(message);}
function eventRow(campaign_id){return db.daily.find(r=>r.campaign_id===campaign_id&&r.scenario==='after'&&r.date==='2026-11-14');}
export async function mockRequest(action,args={}){
  switch(action){
    case 'products':return db.products.map(enriched);
    case 'search':return db.products.filter(p=>relevance(p,args.q)>0&&(!args.category||p.category===args.category)).map(enriched).sort((a,b)=>relevance(b,args.q)-relevance(a,args.q));
    case 'discounts':return clone(db.discounts);
    case 'ads':return ranked(args);
    case 'overview':return overview(args);
    case 'campaigns':return db.campaigns.filter(c=>!args.campaign_id||args.campaign_id===c.campaign_id).map(c=>({...c,...overview({...args,campaign_id:c.campaign_id})}));
    case 'rpi':{const current=overview({...args,scenario:'after'}),baseline=overview({...args,scenario:'before'});return {current,baseline,change_percent:baseline.rpi?(current.rpi/baseline.rpi-1)*100:null};}
    case 'recommendations':return recommendations(args);
    case 'update':{
      const p=db.products.find(p=>p.product_id===args.product_id);if(!p)fail('Товар не найден');
      if(args.in_stock!==undefined)p.in_stock=!!args.in_stock;
      const d=db.discounts.find(d=>d.product_id===p.product_id);
      if(args.percent!==undefined){if(!Number.isFinite(args.percent)||args.percent<0||args.percent>90)fail('Скидка должна быть от 0 до 90%');d.percent=args.percent;}
      if(args.active!==undefined)d.active=!!args.active;
      return enriched(p);
    }
    case 'impression':{
      if(db.impressions[args.impression_id])return clone(db.impressions[args.impression_id]);
      const ad=ranked({q:args.query}).find(p=>p.product_id===args.product_id&&p.campaign_id===args.campaign_id);if(!ad)fail('Объявление больше недоступно');
      const event={...args,created_at:DEMO_DATE,is_demo:true};db.impressions[args.impression_id]=event;
      const row=eventRow(args.campaign_id);row.impressions++;row.relevant_impressions++;row.available_impressions++;
      return clone(event);
    }
    case 'click':{
      if(db.clicks[args.click_id])return clone(db.clicks[args.click_id]);
      const imp=db.impressions[args.impression_id];if(!imp||imp.product_id!==args.product_id||imp.campaign_id!==args.campaign_id)fail('Нет соответствующего показа');
      const existing=Object.values(db.clicks).find(c=>c.impression_id===args.impression_id);if(existing)return clone(existing);
      const event={...args,created_at:DEMO_DATE,is_demo:true};db.clicks[args.click_id]=event;eventRow(imp.campaign_id).clicks++;return clone(event);
    }
    case 'order':{
      if(db.orders[args.order_id])return clone(db.orders[args.order_id]);
      const p=db.products.find(p=>p.product_id===args.product_id);if(!p?.in_stock)fail('Товар недоступен');
      const click=args.click_id?db.clicks[args.click_id]:null;
      if(args.click_id&&(!click||click.product_id!==args.product_id))fail('Клик не соответствует заказу');
      if(click){const existing=Object.values(db.orders).find(o=>o.click_id===click.click_id);if(existing)return clone(existing);}
      const order={...args,campaign_id:click?.campaign_id||null,pharmacy_id:p.pharmacy_id,amount:enriched(p).current_price,status:'confirmed',is_demo:true};
      db.orders[args.order_id]=order;if(click){const row=eventRow(click.campaign_id);row.confirmed_purchases++;row.revenue+=order.amount;}return clone(order);
    }
    case 'reset':return resetMock();
    default:fail('Неизвестное действие демонстратора');
  }
}

