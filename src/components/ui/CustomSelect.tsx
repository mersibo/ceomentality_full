import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';

interface CustomSelectProps<T extends string> {
  value: T;
  options: readonly T[];
  onChange?: (value:T)=>void;
  className?: string;
  placeholder?: string;
}

export function CustomSelect<T extends string>({value,options,onChange,className='',placeholder}:CustomSelectProps<T>) {
  const [open,setOpen]=useState(false);
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{const close=(event:PointerEvent|KeyboardEvent)=>{if(event instanceof KeyboardEvent?event.key==='Escape':!ref.current?.contains(event.target as Node))setOpen(false)};document.addEventListener('pointerdown',close);document.addEventListener('keydown',close);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',close)}},[]);
  return <div className={`custom-select ${open?'open':''} ${className}`} ref={ref}><button type="button" className="custom-select-trigger" onClick={()=>setOpen(!open)}><span>{value||placeholder}</span><i/></button>{open&&<div className="custom-options">{options.map(option=><button type="button" key={option} className={option===value?'selected':''} onClick={()=>{onChange?.(option);setOpen(false)}}>{option}<span>{option===value?<Icon name="check" size={13}/>:null}</span></button>)}</div>}</div>;
}
