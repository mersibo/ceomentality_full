import { useState, type Dispatch, type SetStateAction } from 'react';
import { Icon } from '../ui/Icon';
import { CustomSelect } from '../ui/CustomSelect';
import { buildStatusCounts } from '../../features/candidates/selectors';
import type { AccessBatch, Candidate, WorkspaceFilters } from '../../types/domain';

interface SidebarProps { mode: string; query: string; setQuery: (value: string) => void; filters: WorkspaceFilters; setFilters: Dispatch<SetStateAction<WorkspaceFilters>>; candidates: Candidate[]; drops?: AccessBatch[]; reset: () => void; onClose?: () => void }
interface SelectSideProps { label: string; value: string; onChange: (value: string) => void; options?: string[] }
interface FilterGroupProps { title: string; items: string[]; counts?: Record<string, number>; value: string; setValue: (value: string) => void; radio?: boolean }

export function Sidebar({ mode, query, setQuery, filters, setFilters, candidates, drops = [], reset, onClose }: SidebarProps) {
  const [viewSaved, setViewSaved] = useState(() => Boolean(localStorage.getItem('ceomentality:view')));
  const counts = candidates.length ? buildStatusCounts(candidates) : {};
  const candidatesMode = mode === 'Candidate Dossiers';
  const accessMode = mode === 'Access Codes';
  const waveNames = Array.from(new Set([...drops.map((drop) => drop.name), ...candidates.map((candidate) => candidate.wave)].filter(Boolean)));
  const dropNames = waveNames;
  const dropCounts = drops.reduce<Record<string, number>>((result, drop) => ({ ...result, [drop.status]: (result[drop.status] || 0) + 1 }), {});
  return <aside className="sidebar"><button className="sidebar-drawer-close" onClick={onClose} aria-label="Hide filters"><Icon name="sidebar" size={20} /></button>
    <div className="filter-head"><span>Filters</span><button onClick={reset}>Clear all</button></div>
    {!mode.includes('Analytics') && <label className="search-box"><Icon name="search" size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder={candidatesMode ? 'Search participants...' : 'Search codes or batches...'} /></label>}
    {mode === 'Analytics' && <><SelectSide label="Drop" value={filters.drop || 'All drops'} options={['All drops', ...dropNames]} onChange={v => setFilters({ ...filters, drop: v })} /><SelectSide label="Wave" value={filters.wave === 'All' ? 'All waves' : filters.wave} options={['All waves', ...waveNames]} onChange={v => setFilters({ ...filters, wave: v === 'All waves' ? 'All' : v })} /></>}
    <FilterGroup title="Status" items={candidatesMode ? ['Under review', 'Approved', 'Code assigned', 'Waitlisted', 'Rejected'] : ['Active', 'Scheduled', 'Paused', 'Closed']} counts={candidatesMode ? counts : dropCounts} value={filters.status} setValue={v => setFilters({ ...filters, status: v })} />
    {candidatesMode && <FilterGroup title="Wave" items={waveNames} value={filters.wave} setValue={v => setFilters({ ...filters, wave: v })} radio />}
    {mode === 'Analytics' && <FilterGroup title="Wave" items={waveNames} value={filters.wave} setValue={v => setFilters({ ...filters, wave: v })} radio />}
    {candidatesMode && <FilterGroup title="Expertise" items={['Founder / CEO', 'Investor', 'Product', 'Media / Content', 'Finance', 'Creative / Brand', 'Other']} value={filters.expertise || 'All'} setValue={v => setFilters({ ...filters, expertise: v })} />}
    {accessMode && <><SelectSide label="Drop" value={filters.drop || 'All drops'} options={['All drops', ...dropNames]} onChange={v => setFilters({ ...filters, drop: v })} /><FilterGroup title="Code type" items={['Single-use', 'Multi-use']} value={filters.codeType || 'All'} setValue={v => setFilters({ ...filters, codeType: v })} /><FilterGroup title="Expiry" items={['Expired']} value={filters.expiry || 'All'} setValue={v => setFilters({ ...filters, expiry: v })} /></>}
    <SelectSide label="Source" value={filters.source === 'All' ? 'All sources' : filters.source} options={['All sources', 'Website', 'Telegram bot', 'Partner', 'Referral']} onChange={v => setFilters({ ...filters, source: v === 'All sources' ? 'All' : v })} />
    <button className={`save-view ${viewSaved ? 'saved' : ''}`} onClick={() => { if (viewSaved) { localStorage.removeItem('ceomentality:view'); setViewSaved(false) } else { localStorage.setItem('ceomentality:view', JSON.stringify({ filters, query, mode })); setViewSaved(true) } }}><Icon name="bookmark" />{viewSaved ? 'Saved view' : 'Save view'}</button>
  </aside>;
}

function SelectSide({ label, value, onChange, options = [value] }: SelectSideProps) { return <div className="filter-block"><label>{label}</label><CustomSelect className="side-select" value={value} options={options} onChange={onChange} /></div> }

function FilterGroup({ title, items, counts = {}, value, setValue, radio }: FilterGroupProps) {
  const allLabel = title === 'Wave' ? 'All waves' : title === 'Expertise' ? 'All expertise' : 'All';
  return <div className={`check-group group-${title.toLowerCase().replace(/\s+/g, '-')}`}><h3>{title}</h3><button className="check-row selected" onClick={() => setValue('All')}><span className={`${radio ? 'radio' : 'box'} ${value === 'All' ? 'active' : ''}`} /><span>{allLabel}</span></button>{items.map(x => <button className="check-row" key={x} onClick={() => setValue(x)}><span className={`${radio ? 'radio' : 'box'} ${value === x ? 'active' : ''}`} /><span>{x}</span>{counts[x] != null && <b>{counts[x]}</b>}</button>)}</div>
}
