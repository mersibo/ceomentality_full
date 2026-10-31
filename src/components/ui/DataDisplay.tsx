import type { ReactNode } from 'react';
import { Icon } from './Icon';

export interface MetricItem { label:string; value:ReactNode; delta?:string }
export function MetricStrip({items,compact=false}:{items:MetricItem[];compact?:boolean}) { return <section className={`metric-strip${compact?' compact':''}`}>{items.map(item=><div className="metric" key={item.label}><span>{item.label}</span><strong>{item.value}</strong>{item.delta&&<em>{item.delta}</em>}</div>)}</section> }
export function Info({label,children}:{label:string;children:ReactNode}) { return <div className="info-cell"><label>{label}</label><p>{children}</p></div> }
export function Mini({label,value}:{label:string;value:ReactNode}) { return <div className="metric-mini"><strong>{value}</strong><label>{label}</label></div> }
export function Empty({text}:{text:string}) { return <div className="empty"><Icon name="users" size={28}/><p>{text}</p></div> }
