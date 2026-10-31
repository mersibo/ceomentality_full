import type { ReactNode } from 'react';
import { Icon } from './Icon';

interface ModalProps { title:string; onClose:()=>void; children:ReactNode }

export function Modal({title,onClose,children}:ModalProps) {
  return <div className="modal-backdrop" onMouseDown={event=>event.target===event.currentTarget&&onClose()}><section className="modal"><div className="modal-head"><div><span>CEOMENTALITY MVP</span><h2>{title}</h2></div><button onClick={onClose}><Icon name="x"/></button></div>{children}</section></div>;
}
