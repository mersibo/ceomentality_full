import type { Language } from '../types/domain';
import { translateText } from '../i18n';

let language:Language=localStorage.getItem('ceomentality:language')==='ru'?'ru':'en';
const translatedProps=new Set(['children','label','title','placeholder','aria-label']);
const alwaysEnglish=new Set(['CEOMENTALITY','access system','Simple CRM','Candidate dossier','candidate dossiers','access codes','analytics']);

export function setRuntimeLanguage(next:Language):void { language=next }

function translateValue(value:unknown):unknown {
 if(typeof value==='string')return language==='ru'&&!alwaysEnglish.has(value.trim())?translateText(value,'ru'):value;
 if(Array.isArray(value)){const translated=value.map(translateValue);return translated.some((item,index)=>item!==value[index])?translated:value}
 return value;
}

export function translateProps<T>(props:T):T {
 if(!props||typeof props!=='object')return props;
 const source=props as Record<string,unknown>;
 if(source['data-i18n-static']===true)return props;
 let translated:Record<string,unknown>|undefined;
 let hasRussianText=false;
 for(const key of translatedProps)if(key in source){
  const value=translateValue(source[key]);
  if(value!==source[key]){translated??={...source};translated[key]=value;if(key==='children'||key==='label'||key==='placeholder')hasRussianText=true}
 }
 if(hasRussianText){translated??={...source};translated['data-russian-text']=true}
 return (translated??source) as T;
}
