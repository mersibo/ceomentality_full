import type { AccessBatch, WorkspaceFilters } from '../../types/domain';

export type BatchTab='All'|'Active'|'Scheduled'|'Expired';
export type BatchSort='Recently created'|'Name A-Z'|'Highest issued'|'Most redeemed';

export function selectBatches(batches:AccessBatch[],query:string,filters:WorkspaceFilters,tab:BatchTab,sort:BatchSort):AccessBatch[] {
 const needle=query.trim().toLowerCase();
 return batches.filter(batch=>{
  const source=batch.source||'';
  return (!needle||`${batch.name} ${batch.description} ${batch.code}`.toLowerCase().includes(needle))
   &&(filters.status==='All'||(filters.status==='Redeemed'?batch.redeemed>0:filters.status==='Expired'?batch.status==='Closed':batch.status===filters.status))
   &&(tab==='All'||(tab==='Expired'?batch.status==='Closed':batch.status===tab))
   &&(!filters.drop||filters.drop==='All drops'||batch.name===filters.drop)
   &&(!filters.expiry||filters.expiry==='All'||(filters.expiry==='Expired'&&batch.status==='Closed'))
   &&(!filters.codeType||filters.codeType==='All'||(batch.codeType||'Single-use')===filters.codeType)
   &&(!filters.source||filters.source==='All'||source===filters.source);
 }).sort((a,b)=>sort==='Name A-Z'?a.name.localeCompare(b.name):sort==='Highest issued'?b.issued-a.issued:sort==='Most redeemed'?b.redeemed-a.redeemed:batches.indexOf(a)-batches.indexOf(b));
}
