import type { Candidate } from '../../types/domain';
import { Icon } from '../../components/ui/Icon';

const tone=(status:Candidate['status'])=>['Approved','Code assigned','Code used','Accepted'].includes(status)?'green':status==='Under review'?'blue':status==='Waitlisted'?'orange':'slate';

export function CandidateCard({candidate,onOpen}:{candidate:Candidate;onOpen:(id:string)=>void}) {
 return <article className={`candidate-card ${tone(candidate.status)}`} onClick={()=>onOpen(candidate.id)}><div className="card-status"><span className="status-dot"/><b>{candidate.status}</b><em>{candidate.wave}</em></div><div className="person"><div className="initials">{candidate.initials}</div><div><h2>{candidate.name}</h2><p>{candidate.role}</p><p>{candidate.company}</p></div></div><div className="mini-grid"><div><label>Code assigned</label><strong>{candidate.code||'—'}</strong></div><div><label>Stage</label><span>{candidate.stage==='club'?'Club membership':'Product access'}</span></div></div><div className="notes"><label>Notes</label><p>{candidate.notes.at(-1)||'No notes yet'}</p><label>Summary</label><p>{candidate.summary}</p></div><button className="arrow-link" aria-label="Open dossier" onClick={event=>{event.stopPropagation();onOpen(candidate.id)}}><Icon name="arrow"/></button></article>;
}
