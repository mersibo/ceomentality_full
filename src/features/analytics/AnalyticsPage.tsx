import { useEffect, useState } from 'react';
import { DateRangePicker } from '../../components/ui/DateRangePicker';
import { CustomSelect } from '../../components/ui/CustomSelect';
import { MetricStrip } from '../../components/ui/DataDisplay';
import { Icon } from '../../components/ui/Icon';
import { api } from '../../services/api';
import type { AccessBatch, AnalyticsOverview, Candidate, WorkspaceFilters } from '../../types/domain';

type Granularity='Daily'|'Weekly'|'Monthly';
interface AnalyticsProps { candidates:Candidate[]; drops:AccessBatch[]; filters:WorkspaceFilters; exportData:()=>void }

function queryParams(period:string,granularity:Granularity) {
  const params=new URLSearchParams({granularity:granularity.toLowerCase()});
  const match=period.match(/^([A-Za-z]{3}) (\d{1,2}) - (?:[A-Za-z]{3} )?(\d{1,2}), (\d{4})$/);
  if(match){const [,month,start,end,year]=match;params.set('from',new Date(`${month} ${start}, ${year}`).toISOString().slice(0,10));params.set('to',new Date(`${month} ${end}, ${year}`).toISOString().slice(0,10))}
  return params.toString();
}
function percent(value:number,total:number){return total?Math.round((value/total)*100):0}
function chartPath(values:number[]) {
  if(!values.length)return '';
  return values.map((value,index)=>`${index?'L':'M'}${values.length===1?500:(index/(values.length-1))*960+20} ${220-(Math.max(0,Math.min(100,value))/100)*190}`).join(' ');
}

export function Analytics({candidates,drops,filters,exportData}:AnalyticsProps) {
  const [period,setPeriod]=useState('All time');
  const [granularity,setGranularity]=useState<Granularity>('Daily');
  const [overview,setOverview]=useState<AnalyticsOverview|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{setError('');api.getAnalytics(queryParams(period,granularity)).then(setOverview).catch(err=>setError(err instanceof Error?err.message:'Analytics loading failed'))},[period,granularity,candidates,drops]);
  const summary=overview?.summary||{totalApplications:0,approved:0,rejected:0,underReview:0,codesAssigned:0,codesUsed:0,accepted:0,purchasesConfirmed:0,conversionRate:0,purchaseToClubConversion:0};
  const rows=(overview?.drops||[]).filter(drop=>(!filters.drop||filters.drop==='All drops'||drop.dropName===filters.drop)&&(filters.status==='All'||drop.status===filters.status));
  const series=overview?.timeseries||[];
  const values=series.map(item=>item.conversionRate);
  const total=summary.totalApplications;
  return <main className="content analytics">
    <div className="analytics-head"><div><h1>analytics</h1><p>Server-calculated performance from application to club membership.</p></div><div className="button-row"><DateRangePicker value={period} onChange={setPeriod}/><button className="outline-btn" onClick={exportData}><Icon name="download"/>Export</button></div></div>
    {error&&<div className="search-empty">{error}</div>}
    <MetricStrip items={[{label:'Applications',value:total,delta:`${summary.underReview} under review`},{label:'Approved',value:summary.approved,delta:`${summary.rejected} rejected`},{label:'Codes issued',value:summary.codesAssigned,delta:`${summary.codesUsed} activated`},{label:'Purchases',value:summary.purchasesConfirmed,delta:`${summary.accepted} accepted`},{label:'Conversion rate',value:`${summary.conversionRate}%`,delta:`${summary.purchaseToClubConversion}% purchase to club`} ]}/>
    <section className="analytics-grid">
      <section className="panel funnel-panel"><h3>Overall funnel</h3><div className="funnel-wrap"><div className="funnel-labels"><p>Applications</p><p>Approved</p><p>Codes issued</p><p>Codes activated</p></div><div className="funnel"><div/><div/><div/><div/></div><div className="funnel-values"><p><strong>{total}</strong><span>100%</span></p><p><strong>{summary.approved}</strong><span>{percent(summary.approved,total)}%</span></p><p><strong>{summary.codesAssigned}</strong><span>{percent(summary.codesAssigned,total)}%</span></p><p><strong>{summary.codesUsed}</strong><span>{percent(summary.codesUsed,total)}%</span></p></div></div><div className="conversion-box"><span>Applications to code</span><strong>{summary.conversionRate}%</strong></div></section>
      <section className="panel line-panel"><div className="panel-top"><h3>Conversion over time</h3><CustomSelect className="chart-period" value={granularity} options={['Daily','Weekly','Monthly']} onChange={setGranularity}/></div><div className="chart"><div className="y-axis"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><svg viewBox="0 0 1000 250" aria-label="Conversion rate chart"><path className="grid-line" d="M0 28H1000M0 86H1000M0 144H1000M0 202H1000"/><path className="line" d={chartPath(values)}/></svg><div className="x-axis">{series.slice(-8).map(item=><span key={item.date}>{item.date}</span>)}{!series.length&&<span>No data</span>}</div></div></section>
    </section>
    <section className="panel performance"><h3>Performance by drop / wave</h3><table><thead><tr><th>Drop / wave</th><th>Status</th><th>Applications</th><th>Approved</th><th>Rejected</th><th>Codes issued</th><th>Activated</th><th>Conversion</th></tr></thead><tbody>{rows.map(drop=><tr key={drop.dropId}><td><strong>{drop.dropName}</strong><span>{drop.validity}</span></td><td><span className={`table-status ${drop.status!=='Active'?'blue':''}`}>{drop.status}</span></td><td>{drop.applications}</td><td>{drop.approved}</td><td>{drop.rejected}</td><td>{drop.codesIssued}</td><td>{drop.codesActivated}</td><td>{drop.conversionRate.toFixed(1)}%</td></tr>)}</tbody></table>{!rows.length&&<div className="search-empty">No drop data for selected filters</div>}</section>
    <section className="panel insights"><h3>Current state</h3><div className="insight-row"><div><span><Icon name="trend"/></span><p>{summary.underReview} applications await a decision.</p></div><div><span><Icon name="target"/></span><p>{summary.purchasesConfirmed} purchases are confirmed.</p></div><div><span><Icon name="users"/></span><p>{summary.accepted} candidates are accepted into the club.</p></div></div></section>
  </main>;
}
