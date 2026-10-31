import { useState } from 'react';
import type { Candidate, CandidateStatus, WorkspaceFilters } from '../../types/domain';
import { CustomSelect } from '../../components/ui/CustomSelect';
import { Empty, MetricStrip } from '../../components/ui/DataDisplay';
import { Icon } from '../../components/ui/Icon';
import { CandidateCard } from './CandidateCard';
import { countCandidateStatus, selectCandidates, type CandidateSort } from './selectors';

interface DossiersProps { candidates:Candidate[]; open:(id:string)=>void; query:string; filters:WorkspaceFilters }

export function Dossiers({candidates,open,query,filters}:DossiersProps) {
  const [sort,setSort]=useState<CandidateSort>('Recently updated');
  const [view,setView]=useState<'grid'|'list'>('grid');
  const visible=selectCandidates(candidates,query,filters,sort);
  const count=(status:CandidateStatus)=>countCandidateStatus(candidates,status);
  const share=(status:CandidateStatus)=>candidates.length?`${((count(status)/candidates.length)*100).toFixed(1)}%`:'0%';
  return <main className="content dossiers"><div className="hero-row"><div><div className="pretitle">Simple CRM</div><h1>candidate dossiers</h1><p>A simple CRM with dossiers for every participant in your access pipeline.</p></div><MetricStrip compact items={[{label:'Total participants',value:candidates.length,delta:`${candidates.length} records`},{label:'Under review',value:count('Under review'),delta:share('Under review')},{label:'Approved',value:count('Approved'),delta:share('Approved')},{label:'Code assigned',value:count('Code assigned'),delta:share('Code assigned')} ]}/></div><div className="list-head"><span>{visible.length} participants</span><div className="dossier-view-actions"><div className="inline-sort"><span>Sort by:</span><CustomSelect value={sort} options={['Recently updated','Newest first','Name A-Z']} onChange={setSort}/></div><button className={`view-switch ${view}`} aria-label="Switch candidate view" onClick={()=>setView(view==='grid'?'list':'grid')}><Icon name="grid" size={14}/><span/><Icon name="list" size={15}/></button></div></div><section className={`cards-grid ${view}`}>{visible.map(c=><CandidateCard key={c.id} candidate={c} onOpen={open}/>)}</section>{!visible.length&&<Empty text="No candidates match these filters."/>}</main>;
}
