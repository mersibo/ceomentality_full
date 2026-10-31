import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Icon } from '../../components/ui/Icon';
import { Info } from '../../components/ui/DataDisplay';
import { Modal } from '../../components/ui/Modal';
import { CustomSelect } from '../../components/ui/CustomSelect';
import { api } from '../../services/api';
import { copyText } from '../../services/clipboard';
import type { AccessBatch, Candidate, CandidateProfile, CandidateStatus } from '../../types/domain';

interface DossierProps {
  candidate: Candidate;
  drops: AccessBatch[];
  back: () => void;
  update: (candidate: Candidate) => void | Promise<void>;
  decide: (status: CandidateStatus) => void | Promise<void>;
  assignCode: () => void | Promise<void>;
  updatePurchase: (confirmed:boolean, product:string) => void | Promise<void>;
  updateMembership: (addedToGroups:boolean) => void | Promise<void>;
  assignDrop: (dropName:string) => void | Promise<void>;
  addNote: (note: string) => void | Promise<void>;
  notify: (message: string) => void;
  onPrevious: () => void;
  onNext: () => void;
}

const entries = (value?: Record<string, unknown>) => Object.entries(value || {}).filter(([, item]) => item !== undefined && item !== null && item !== '');
const listProjects = (projects?: Array<Record<string, unknown>>) => (projects || []).map((project, index) => String(project.name || project.title || project.url || project.description || `Project ${index + 1}`));

export function Dossier({ candidate, drops, back, update, decide, assignCode, updatePurchase, updateMembership, assignDrop, addNote, notify, onPrevious, onNext }: DossierProps) {
  const [note, setNote] = useState('');
  const [panelTab, setPanelTab] = useState<'notes'|'activity'>('notes');
  const [candidateMenu, setCandidateMenu] = useState(false);
  const [codeModal, setCodeModal] = useState(false);
  const [timelineModal, setTimelineModal] = useState(false);
  const [profile,setProfile]=useState<CandidateProfile|null>(null);
  const noteInput = useRef<HTMLInputElement>(null);
  const questionnaire = entries(candidate.questionnaireAnswers);
  const socialLinks = entries(candidate.socialLinks);
  const projects = listProjects(candidate.projects);
  const achievements = candidate.achievements || [];
  const comments = candidate.managerComments || [];
  const history = profile?.history || [];
  const applications = profile?.applications || [candidate];

  useEffect(()=>{api.getCandidateProfile(candidate.id).then(setProfile).catch(()=>setProfile(null))},[candidate.id,candidate.status,candidate.code,candidate.purchaseConfirmed,candidate.addedToGroupsAt]);
  useEffect(() => {
    const close = (event: PointerEvent) => { const target = event.target; if (target instanceof Element && !target.closest('.candidate-actions-menu')) setCandidateMenu(false) };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, []);

  const action = (status: CandidateStatus) => void decide(status);
  const approveTarget:CandidateStatus = candidate.stage==='club'&&candidate.status==='Approved'?'Accepted':'Approved';
  const canReview=['Under review','Waitlisted'].includes(candidate.status);
  const canReject=['Under review','Waitlisted','Approved'].includes(candidate.status);
  const canAssign=candidate.stage==='purchase'&&candidate.status==='Approved'&&!candidate.code;
  const exportCandidate = () => { const blob = new Blob([JSON.stringify({candidate,profile}, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `${candidate.id}-dossier.json`; link.click(); URL.revokeObjectURL(url); setCandidateMenu(false) };

  return <>
    <main className="content dossier-detail">
      <div className="detail-topline"><button className="back-link" onClick={back}><Icon name="left" />Back to dossiers</button><div className="pager"><button onClick={onPrevious}><Icon name="left" size={15} />Previous</button><button onClick={onNext}>Next <Icon name="arrow" size={15} /></button></div></div>
      <section className="detail-hero">
        <div className="detail-title"><div className="pretitle">Candidate dossier</div><h1>{candidate.name}</h1><p>{candidate.role || 'No role'} <span>-</span> {candidate.company || 'No company'}</p>
          <div className="detail-actions">
            {(canReview||approveTarget==='Accepted')&&<button className="primary-btn" onClick={()=>action(approveTarget)}><Icon name="check" />{approveTarget==='Accepted'?'Accept':'Approve'}</button>}
            {canReview&&candidate.status!=='Waitlisted'&&<button className="outline-btn" onClick={()=>action('Waitlisted')}>Hold</button>}
            {canReject&&<button className="outline-btn" onClick={()=>action('Rejected')}><Icon name="x" />Reject</button>}
            {canAssign&&<button className="outline-btn wide" onClick={()=>void assignCode()}><Icon name="link" />Assign code</button>}
            <div className="candidate-actions-menu"><button className="outline-btn square" aria-label="More actions" onClick={()=>setCandidateMenu(!candidateMenu)}><Icon name="more" size={18}/></button>{candidateMenu&&<div className="context-menu"><button onClick={()=>void copyText(candidate.telegram).then(()=>notify('Telegram copied')).catch(()=>notify('Telegram copy failed'))}>Copy Telegram</button><button onClick={exportCandidate}>Export dossier</button>{candidate.status!=='Archived'&&<button className="danger" onClick={()=>action('Archived')}>Archive candidate</button>}</div>}</div>
          </div>
        </div>
        <div className="detail-status panel"><Info label="Status"><span className="blue-pill">{candidate.status}</span></Info><Info label="Drop">{candidate.wave||'Not assigned'}</Info><Info label="Stage">{candidate.stage==='club'?'Club membership':'Purchase application'}</Info><Info label="Source">{candidate.source}</Info><Info label="Code delivery">{candidate.deliveryChannel==='email'?'Email':'Telegram'}</Info><Info label="Location">{candidate.country||'Not specified'}</Info><Info label="Telegram">{candidate.telegram||'Not specified'}</Info><Info label="Applied">{candidate.appliedAt}</Info><Info label="Related applications">{applications.length}</Info></div>
      </section>

      <section className="detail-grid">
        <section className="panel profile-panel"><h3>Unified profile</h3><p>{candidate.summary||'No summary yet.'}</p><div className="detail-table three"><Info label="Company">{candidate.company||'-'}</Info><Info label="Role">{candidate.role||'-'}</Info><Info label="Expertise">{candidate.expertise||'-'}</Info><Info label="Country">{candidate.country||'-'}</Info><Info label="Projects">{projects.length}</Info><Info label="Achievements">{achievements.length}</Info></div><label>Application history</label><div className="tag-row">{applications.map(item=><span key={item.id}>{item.stage}: {item.status} ({item.appliedAt})</span>)}</div></section>

        <section className="panel access-code-panel"><div className="panel-top"><h3>Access & purchase</h3><button className="outline-btn small" onClick={()=>setCodeModal(true)}>View details</button></div>{candidate.stage==='purchase'&&!candidate.code&&<><label>Assigned drop</label><CustomSelect value={candidate.wave||''} options={drops.filter(drop=>drop.status!=='Closed').map(drop=>drop.name)} placeholder="Select a drop" onChange={value=>void assignDrop(value)}/></>}<div className="detail-table three"><Info label="Code"><b>{candidate.code||'-'}</b></Info><Info label="Drop">{candidate.wave||'Not assigned'}</Info><Info label="Redeemed">{candidate.status==='Code used'?'Yes':'No'}</Info><Info label="Purchase">{candidate.purchaseConfirmed?'Confirmed':'Not confirmed'}</Info><Info label="Product">{candidate.product||'-'}</Info><Info label="Groups">{candidate.addedToGroupsAt?'Added':'Not added'}</Info></div><div className="button-row">{candidate.stage==='purchase'&&<button className="outline-btn" onClick={()=>void updatePurchase(!candidate.purchaseConfirmed,candidate.product||'Cardholder')}>{candidate.purchaseConfirmed?'Cancel purchase confirmation':'Confirm purchase'}</button>}{candidate.stage==='club'&&candidate.status==='Accepted'&&<button className="outline-btn" onClick={()=>void updateMembership(!candidate.addedToGroupsAt)}>{candidate.addedToGroupsAt?'Mark removed from groups':'Mark added to groups'}</button>}</div></section>

        <section className="panel profile-panel"><h3>Application data</h3><div className="detail-table three">{questionnaire.length?questionnaire.map(([key,value])=><Info label={key} key={key}>{String(value)}</Info>):<Info label="Questionnaire">No answers saved</Info>}{socialLinks.map(([key,value])=><Info label={key} key={key}>{String(value)}</Info>)}</div><label>Projects</label><div className="tag-row">{projects.length?projects.map(item=><span key={item}>{item}</span>):<span>No projects</span>}</div><label>Achievements</label><div className="tag-row">{achievements.length?achievements.map(item=><span key={item}>{item}</span>):<span>No achievements</span>}</div></section>

        <section className="panel notes-panel"><div className="panel-top"><h3>Notes & activity</h3><button className="outline-btn small" onClick={()=>{setPanelTab('notes');requestAnimationFrame(()=>noteInput.current?.focus())}}><Icon name="plus" size={14}/>Add note</button></div><div className="tabs tight"><button className={panelTab==='notes'?'active':''} onClick={()=>setPanelTab('notes')}>Notes ({candidate.notes.length+comments.length})</button><button className={panelTab==='activity'?'active':''} onClick={()=>setPanelTab('activity')}>Activity ({history.length})</button></div>{panelTab==='activity'?<div className="dossier-activity-feed">{history.map(item=><div key={item.id}><span className="history-step active"/><p>{item.detail}</p><time>{new Date(item.at).toLocaleString()}</time></div>)}{!history.length&&<p>No activity yet</p>}</div>:<><div className="note-list">{[...candidate.notes,...comments].map((item,index)=><div className="note-row" key={`${item}-${index}`}><span className="mini-avatar">CM</span><div><strong>Manager</strong><em>Private note</em><p>{item}</p></div></div>)}</div><form className="note-form" onSubmit={(event:FormEvent)=>{event.preventDefault();if(note.trim()){void addNote(note.trim());setNote('')}}}><input ref={noteInput} value={note} onChange={event=>setNote(event.target.value)} placeholder="Add internal comment..."/><button type="submit" className="primary-btn">Add note</button></form></>}</section>

        <section className="panel eligibility-panel"><h3>Eligibility & participation</h3><div className="eligibility-layout"><div className="eligibility-stats"><Info label="Current member status"><strong>{String(candidate.memberProfile?.status||(candidate.status==='Accepted'?'member':'candidate'))}</strong></Info><Info label="Decision">{String(candidate.decision?.status||candidate.status)}</Info><Info label="Purchase confirmed">{candidate.purchaseConfirmed?'Yes':'No'}</Info><Info label="Added to groups">{candidate.addedToGroupsAt?new Date(candidate.addedToGroupsAt).toLocaleString():'No'}</Info></div><div className="approval-history"><label>Latest events</label>{history.slice(0,4).map(item=><div className="history-step done" key={item.id}><span/><p>{item.detail}</p><time>{new Date(item.at).toLocaleDateString()}</time></div>)}<button className="wide-outline" onClick={()=>setTimelineModal(true)}>View full timeline <Icon name="arrow" size={14}/></button></div></div></section>
      </section>
    </main>
    {codeModal&&<Modal title="Access details" onClose={()=>setCodeModal(false)}><div className="batch-detail-modal"><div><span>Candidate</span><strong>{candidate.name}</strong></div><div><span>Code</span><strong>{candidate.code||'No code assigned'}</strong></div><div><span>Drop</span><strong>{candidate.wave||'No active drop'}</strong></div><div><span>Purchase</span><strong>{candidate.purchaseConfirmed?'Confirmed':'Not confirmed'}</strong></div></div><div className="form-actions"><button className="outline-btn" disabled={!candidate.code} onClick={()=>candidate.code&&void copyText(candidate.code).then(()=>notify('Code copied')).catch(()=>notify('Code copy failed'))}>Copy code</button>{canAssign&&<button className="primary-btn" onClick={()=>{void assignCode();setCodeModal(false)}}>Assign code</button>}</div></Modal>}
    {timelineModal&&<Modal title="User history" onClose={()=>setTimelineModal(false)}><div className="modal-timeline">{history.map(item=><div className="done" key={item.id}><span/><div><strong>{item.detail}</strong><small>{new Date(item.at).toLocaleString()}</small></div></div>)}</div><div className="form-actions"><button className="primary-btn" onClick={()=>setTimelineModal(false)}>Close</button></div></Modal>}
  </>;
}
