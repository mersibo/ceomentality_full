import { useEffect, useState } from 'react';
import { Icon } from '../ui/Icon';
import { languages } from '../../i18n';
import { api } from '../../services/api';
import type { AdminUser, AppRoute, Candidate, Language, NotificationState } from '../../types/domain';

const tabs:Exclude<AppRoute,'Profile'>[]=['Candidate Dossiers','Access Codes','Email','Orders','Analytics','Blacklist','Team'];
type Panel='search'|'notifications'|'profile'|null;
interface HeaderProps { active:string; navigate:(route:AppRoute)=>void; candidates:Candidate[]; user:AdminUser; notifications:NotificationState; markNotificationRead:(id:string)=>Promise<void>; markAllNotificationsRead:()=>Promise<void>; openCandidate:(id:string)=>void; openProfile:()=>void; onLogout:()=>void; language:Language; setLanguage:(language:Language)=>void; hasSidebar:boolean; desktopSidebarOpen:boolean; mobileSidebarOpen:boolean; toggleSidebar:()=>void }
interface NotificationProps { tone:string; title:string; text:string; time:string; onOpen:()=>void }

export function Header({active,navigate,user,notifications,markNotificationRead,markAllNotificationsRead,openCandidate,openProfile,onLogout,language,setLanguage,hasSidebar,desktopSidebarOpen,mobileSidebarOpen,toggleSidebar}:HeaderProps) {
  const [panel,setPanel]=useState<Panel>(null);
  const [search,setSearch]=useState('');
  const [results,setResults]=useState<Candidate[]>([]);
  useEffect(()=>{if(!search.trim()){setResults([]);return}const timer=setTimeout(()=>{api.search(search).then((result)=>setResults(result.candidates.slice(0,6))).catch(()=>setResults([]))},250);return()=>clearTimeout(timer)},[search]);
  const close=()=>{setPanel(null);setSearch('')};
  const closeMobileSidebar=()=>{if(mobileSidebarOpen)toggleSidebar()};
  return <header className="topbar"><button className="brand" onClick={()=>{close();closeMobileSidebar();navigate('Candidate Dossiers')}} aria-label="Open candidate dossiers">CEOMENTALITY</button><div className="system-label">access system</div>{hasSidebar&&<button className="header-sidebar-toggle header-sidebar-toggle-mobile" onClick={toggleSidebar} aria-label={mobileSidebarOpen?'Hide filters':'Show filters'} aria-expanded={mobileSidebarOpen}><Icon name="sidebar" size={20}/></button>}<nav className="main-nav">{tabs.filter(t=>t!=='Team'||user.role==='founder').map(t=><button key={t} className={active===t?'active':''} onClick={()=>{close();closeMobileSidebar();navigate(t)}}>{t}</button>)}</nav><div className="top-actions">{hasSidebar&&<button className="header-sidebar-toggle header-sidebar-toggle-desktop" onClick={toggleSidebar} aria-label={desktopSidebarOpen?'Hide filters':'Show filters'} aria-expanded={desktopSidebarOpen}><Icon name="sidebar" size={20}/></button>}<button className={`language-switch ${language}`} onClick={()=>setLanguage(language==='en'?'ru':'en')} aria-label="Switch interface language"><span>{languages.en}</span><i/><span>{languages.ru}</span></button>
    <button className={`icon-btn ${panel==='search'?'is-open':''}`} aria-label="Search" onClick={()=>setPanel(panel==='search'?null:'search')}><Icon name="search"/></button>
    <button className={`icon-btn notification-trigger ${panel==='notifications'?'is-open':''}`} aria-label="Notifications" onClick={()=>setPanel(panel==='notifications'?null:'notifications')}><Icon name="bell"/>{notifications.unread>0&&<span className="notification-dot"/>}</button>
    <button className={`avatar ${panel==='profile'?'is-open':''}`} onClick={()=>setPanel(panel==='profile'?null:'profile')}>{user.name.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase()}</button>
  </div>
  {panel&&<button className="header-scrim" aria-label="Close" onClick={close}/>}
  {panel==='search'&&<section className="header-popover search-popover"><div className="popover-kicker">Global search</div><label className="global-search-field"><Icon name="search"/><input autoFocus value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search candidates..."/><kbd>ESC</kbd></label><div className="search-results">{!search&&<div className="search-hint"><strong>Search candidates</strong><p>Enter a name, company or Telegram username.</p></div>}{search&&results.map(c=><button key={c.id} onClick={()=>{close();openCandidate(c.id)}}><span className="result-avatar">{c.initials}</span><span><strong>{c.name}</strong><small>{c.role} · {c.company}</small></span><em>{c.status}</em></button>)}{search&&!results.length&&<div className="search-empty">No matching records</div>}</div></section>}
  {panel==='notifications'&&<section className="header-popover notifications-popover"><div className="popover-title"><div><span>Activity center</span><h2>Notifications</h2></div><button onClick={()=>void markAllNotificationsRead()}>Mark all read</button></div><div className="notification-list">{notifications.items.slice(0,8).map(event=><Notification key={event.id} tone={activityTone(event.type)} title={event.type.replaceAll('.',' ')} text={event.detail} time={relativeTime(event.createdAt)} onOpen={()=>{void markNotificationRead(event.id);close();if(event.entityType==='candidate'&&event.entityId)openCandidate(event.entityId);else navigate(event.entityType==='drop'?'Access Codes':'Candidate Dossiers')}}/>)}{!notifications.items.length&&<div className="search-empty">No notifications yet</div>}</div></section>}
  {panel==='profile'&&<section className="header-popover profile-menu"><div className="profile-menu-head"><span className="profile-menu-avatar">{user.name.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase()}</span><div><strong>{user.name}</strong><small>{user.email}</small></div></div><div className="profile-role"><span>Workspace role</span><b>{user.role}</b></div><button onClick={()=>{close();openProfile()}}>Profile & settings <Icon name="arrow" size={14}/></button><button className="danger-menu" onClick={()=>{close();onLogout()}}>Sign out</button></section>}
  </header>;
}

function Notification({tone,title,text,time,onOpen}:NotificationProps) { return <button className="notification-item" onClick={onOpen}><span className={`notification-mark ${tone}`}/><span><strong>{title}</strong><p>{text}</p><time>{time} ago</time></span></button> }

function activityTone(type:string) { return type.startsWith('code.')?'green':type.startsWith('drop.')?'orange':'blue' }
function relativeTime(value:string) {
  const seconds=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/1000));
  if(seconds<60)return `${seconds}s`;
  if(seconds<3600)return `${Math.floor(seconds/60)} min`;
  if(seconds<86400)return `${Math.floor(seconds/3600)} h`;
  return `${Math.floor(seconds/86400)} d`;
}
