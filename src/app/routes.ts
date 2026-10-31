import type { AppRoute } from '../types/domain';

const paths:Record<AppRoute,string>={
 'Candidate Dossiers':'/candidates',
 'Access Codes':'/access-codes',
 Email:'/email',
 Orders:'/orders',
 Analytics:'/analytics',
 Blacklist:'/blacklist',
 Team:'/team',
 Profile:'/profile'
};

export interface RouteState { page:AppRoute; candidateId:string|null }

export function parseRoute(pathname=window.location.pathname):RouteState {
 const candidateMatch=pathname.match(/^\/candidates\/([^/]+)$/);
 if(candidateMatch?.[1])return {page:'Candidate Dossiers',candidateId:decodeURIComponent(candidateMatch[1])};
 const page=(Object.entries(paths).find(([,path])=>path===pathname)?.[0] as AppRoute|undefined)??'Candidate Dossiers';
 return {page,candidateId:null};
}

export function routePath(page:AppRoute,candidateId?:string|null):string {
 return page==='Candidate Dossiers'&&candidateId?`/candidates/${encodeURIComponent(candidateId)}`:paths[page];
}

export function writeRoute(page:AppRoute,candidateId?:string|null,replace=false):void {
 const path=routePath(page,candidateId);
 if(window.location.pathname===path)return;
 window.history[replace?'replaceState':'pushState']({},'',path);
}
