import { useState, type FormEvent } from 'react';
import { Modal } from '../../components/ui/Modal';
import type { DropDraft } from '../../types/domain';

export function DropForm({onClose,onSubmit}:{onClose:()=>void;onSubmit:(draft:DropDraft)=>void}) {
 const [form,setForm]=useState<DropDraft>({name:'',description:'',issued:0,validity:'30 days',code:''});
 const submit=(event:FormEvent)=>{event.preventDefault();onSubmit(form)};
 return <Modal title="Create drop" onClose={onClose}><form className="form-grid" onSubmit={submit}><label>Drop name<input required value={form.name} onChange={event=>setForm({...form,name:event.target.value})}/></label><label>Validity<input required value={form.validity} onChange={event=>setForm({...form,validity:event.target.value})}/></label><label className="full">Description<input value={form.description} onChange={event=>setForm({...form,description:event.target.value})}/></label><label className="full">Code prefix<input value={form.code} placeholder="Leave blank to use CM" onChange={event=>setForm({...form,code:event.target.value})}/></label><div className="form-actions"><button type="button" className="outline-btn" onClick={onClose}>Cancel</button><button type="submit" className="primary-btn">Create drop</button></div></form></Modal>;
}
