import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { api } from './services/api';
import { setRuntimeLanguage } from './i18n-runtime/shared';
import { Icon } from './components/ui/Icon';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { CandidateForm } from './features/candidates/CandidateForm';
import { Dossiers } from './features/candidates/DossiersPage';
import { Dossier } from './features/candidates/DossierPage';
import { DropForm } from './features/access/DropForm';
import { Access } from './features/access/AccessPage';
import { Analytics } from './features/analytics/AnalyticsPage';
import { BlacklistPage } from './features/blacklist/BlacklistPage';
import { OrdersPage } from './features/orders/OrdersPage';
import { EmailPage } from './features/email/EmailPage';
import { ProfilePage } from './features/profile/ProfilePage';
import { TeamPage } from './features/team/TeamPage';
import { LoginPage } from './features/auth/LoginPage';
import { ErrorBoundary } from './app/ErrorBoundary';
import { parseRoute, writeRoute } from './app/routes';
import type {
  AccessBatch,
  AdminUser,
  AppRoute,
  BatchDraft,
  BlacklistDraft,
  BlacklistEntry,
  Candidate,
  CandidateDraft,
  CandidateStatus,
  DropDraft,
  Language,
  NotificationState,
  SavedView,
  StoreOrder,
  WorkspaceFilters,
  WorkspaceState,
} from './types/domain';
import './styles.css';
import './styles/sidebar-responsive-fix.css';

const defaultFilters: WorkspaceFilters = { status: 'All', wave: 'All', source: 'All', expertise: 'All' };
const emptyNotifications: NotificationState = { items: [], unread: 0 };
const getSavedView = (): SavedView | null => {
  try { return JSON.parse(localStorage.getItem('ceomentality:view') || 'null') as SavedView | null }
  catch { return null }
};
const resetAllFilters = (): WorkspaceFilters => ({ status: 'All', wave: 'All', source: 'All', expertise: 'All', codeType: 'All', expiry: 'All', drop: 'All drops' });
const runPageTransition = (update: () => void) => {
  if (!document.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { update(); return }
  document.startViewTransition(() => flushSync(update));
};

function App() {
  const initialRoute = parseRoute();
  const [state, setState] = useState<WorkspaceState | null>(null);
  const [blacklist, setBlacklist] = useState<BlacklistEntry[]>([]);
  const [orders, setOrders] = useState<StoreOrder[]>([]);
  const [notifications, setNotifications] = useState<NotificationState>(emptyNotifications);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [active, setActive] = useState<AppRoute>(initialRoute.page);
  const [selected, setSelected] = useState<string | null>(initialRoute.candidateId);
  const [query, setQuery] = useState(() => getSavedView()?.query || '');
  const [filters, setFilters] = useState<WorkspaceFilters>(() => getSavedView()?.filters || defaultFilters);
  const [modal, setModal] = useState<'candidate' | 'drop' | null>(null);
  const [toast, setToast] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('ceomentality:sidebar') === 'collapsed');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem('ceomentality:language') === 'ru' ? 'ru' : 'en');

  const notify = (message: string) => { setToast(message); setTimeout(() => setToast(''), 2600) };
  const reloadWorkspace = async () => {
    const [workspace, entries, notificationState, storeOrders] = await Promise.all([api.load(), api.listBlacklist(), api.notifications(), api.listOrders()]);
    setState(workspace);
    setBlacklist(entries);
    setNotifications(notificationState);
    setOrders(storeOrders);
  };

  useEffect(() => {
    api.session()
      .then(({ user }) => { setCurrentUser(user); setAuthenticated(Boolean(user)) })
      .catch(() => { setCurrentUser(null); setAuthenticated(false) });
  }, []);
  useEffect(() => {
    if (authenticated !== true) return;
    reloadWorkspace().catch((error) => {
      setAuthenticated(false);
      setState(null);
      notify(error instanceof Error ? error.message : 'Workspace loading failed');
    });
  }, [authenticated]);
  useEffect(() => {
    const onPopState = () => { const route = parseRoute(); runPageTransition(() => { setActive(route.page); setSelected(route.candidateId) }) };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);
  useEffect(() => {
    setRuntimeLanguage(language);
    localStorage.setItem('ceomentality:language', language);
    document.documentElement.lang = language;
  }, [language]);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 900px)');
    const update = () => { if (!media.matches) setMobileSidebarOpen(false) };
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  const login = async (credentials: { email: string; password: string }) => {
    try {
      const { user } = await api.login(credentials);
      setCurrentUser(user);
      setAuthenticated(true);
      writeRoute(active, selected, true);
    } catch (error) { notify(error instanceof Error ? error.message : 'Sign in failed') }
  };
  const logout = async () => {
    try { await api.logout() } finally {
      setAuthenticated(false);
      setCurrentUser(null);
      setState(null);
      setActive('Candidate Dossiers');
      setSelected(null);
      window.history.replaceState({}, '', '/login');
    }
  };

  if (authenticated === null) return <div className="loading">Checking session...</div>;
  if (!authenticated) return <LoginPage onLogin={login} />;
  if (!state || !currentUser) return <div className="loading">Loading workspace...</div>;

  const upsertCandidate = (candidate: Candidate) => setState((current) => current ? { ...current, candidates: current.candidates.map((item) => item.id === candidate.id ? candidate : item) } : current);
  const upsertDrop = (drop: AccessBatch) => setState((current) => current ? { ...current, drops: current.drops.map((item) => item.id === drop.id ? drop : item) } : current);
  const updateCandidate = async (candidate: Candidate) => { try { upsertCandidate(await api.updateCandidate(candidate.id, candidate)); notify('Candidate updated') } catch (error) { notify(error instanceof Error ? error.message : 'Candidate update failed') } };
  const decideCandidate = async (id: string, status: CandidateStatus) => { try { upsertCandidate(await api.decideCandidate(id, { status })); await reloadWorkspace(); notify(`Candidate status: ${status}`) } catch (error) { notify(error instanceof Error ? error.message : 'Decision failed') } };
  const addCandidateNote = async (id: string, note: string) => { try { upsertCandidate(await api.addCandidateNote(id, note)); notify('Note added') } catch (error) { notify(error instanceof Error ? error.message : 'Note failed') } };
  const assignCandidateCode = async (id: string) => { try { await api.assignCandidateCode(id); await reloadWorkspace(); notify('Access code assigned from active drop') } catch (error) { notify(error instanceof Error ? error.message : 'Code assignment failed') } };
  const updatePurchase = async (id:string, confirmed:boolean, product:string) => { try { upsertCandidate(await api.updatePurchase(id,{confirmed,product})); notify('Purchase information updated') } catch(error) { notify(error instanceof Error?error.message:'Purchase update failed') } };
  const updateMembership = async (id:string, addedToGroups:boolean) => { try { upsertCandidate(await api.updateMembership(id,{addedToGroups})); notify('Membership information updated') } catch(error) { notify(error instanceof Error?error.message:'Membership update failed') } };
  const assignCandidateDrop = async (id:string, wave:string) => { try { upsertCandidate(await api.updateCandidate(id,{wave})); notify(`Candidate assigned to ${wave}`) } catch(error) { notify(error instanceof Error?error.message:'Drop assignment failed') } };
  const addCandidate = async (draft: CandidateDraft) => { try { const candidate = await api.createCandidate(draft); setState((current) => current ? { ...current, candidates: [candidate, ...current.candidates] } : current); setModal(null); notify('Candidate created') } catch (error) { notify(error instanceof Error ? error.message : 'Candidate creation failed') } };
  const addDrop = async (draft: DropDraft) => { try { const drop = await api.createDrop(draft); setState((current) => current ? { ...current, drops: [drop, ...current.drops] } : current); setModal(null); notify('Drop created') } catch (error) { notify(error instanceof Error ? error.message : 'Drop creation failed') } };
  const generateBatch = async (draft: BatchDraft) => { try { await api.createCodeBatch(draft); await reloadWorkspace(); notify(`${draft.quantity} codes generated`) } catch (error) { notify(error instanceof Error ? error.message : 'Code generation failed') } };
  const regenerateDropCode = async (id: string) => { try { const drop=await api.generateDropCode(id); upsertDrop(drop); notify(`New drop code generated: ${drop.code}`) } catch(error) { notify(error instanceof Error?error.message:'Drop code generation failed') } };
  const activateDrop = async (id: string) => { try { const drop = await api.activateDrop(id); await reloadWorkspace(); notify(`${drop.name} activated`) } catch (error) { notify(error instanceof Error ? error.message : 'Drop activation failed') } };
  const closeDrop = async (id: string) => { try { upsertDrop(await api.closeDrop(id)); notify('Drop closed') } catch (error) { notify(error instanceof Error ? error.message : 'Drop close failed') } };
  const deleteDrop = async (id: string) => { try { await api.deleteDrop(id); setState(current => current ? { ...current, drops: current.drops.filter(drop => drop.id !== id) } : current); notify('Drop deleted') } catch (error) { notify(error instanceof Error ? error.message : 'Drop deletion failed'); throw error } };
  const issueDropCodes = async (id: string) => { try { const result = await api.issueDropCodeToApproved(id); await reloadWorkspace(); const skipped=result.skippedTelegram.length?`, ${result.skippedTelegram.length} without Telegram ID`:''; notify(`${result.queuedToTelegram.length} Telegram messages queued${skipped}`) } catch (error) { notify(error instanceof Error ? error.message : 'Code issuing failed') } };
  const addBlacklistEntry = async (draft: BlacklistDraft) => { try { const entry = await api.addBlacklistEntry(draft); setBlacklist((current) => [entry, ...current]); notify('Person added to blacklist') } catch (error) { notify(error instanceof Error ? error.message : 'Blacklist update failed'); throw error } };
  const removeBlacklistEntry = async (id: string) => { try { await api.removeBlacklistEntry(id); setBlacklist((current) => current.filter((entry) => entry.id !== id)); notify('Person removed from blacklist') } catch (error) { notify(error instanceof Error ? error.message : 'Blacklist update failed') } };
  const refundOrder = async (id:string) => { try { const updated=await api.refundOrder(id); setOrders(current=>current.map(order=>order.id===id?updated:order)); notify('Full refund requested') } catch(error) { notify(error instanceof Error?error.message:'Refund failed'); throw error } };
  const completeOrder = async (id:string) => { try { const updated=await api.completeOrder(id); setOrders(current=>current.map(order=>order.id===id?updated:order)); notify('Order completed and closing receipt sent') } catch(error) { notify(error instanceof Error?error.message:'Order completion failed'); throw error } };
  const createShipment = async (id:string) => { try { const updated=await api.createShipment(id); setOrders(current=>current.map(order=>order.id===id?updated:order)); notify('CDEK shipment created') } catch(error) { notify(error instanceof Error?error.message:'CDEK shipment creation failed'); throw error } };
  const refreshShipment = async (id:string) => { try { const updated=await api.refreshShipment(id); setOrders(current=>current.map(order=>order.id===id?updated:order)); notify('CDEK shipment refreshed') } catch(error) { notify(error instanceof Error?error.message:'CDEK shipment refresh failed'); throw error } };
  const deleteOrder = async (id:string) => { try { await api.deleteOrder(id); setOrders(current=>current.filter(order=>order.id!==id)); notify('Order deleted') } catch(error) { notify(error instanceof Error?error.message:'Order deletion failed'); throw error } };
  const exportData = () => { const url = URL.createObjectURL(api.export(state)); const a = document.createElement('a'); a.href = url; a.download = 'ceomentality-export.json'; a.click(); URL.revokeObjectURL(url); notify('Workspace exported') };
  const markNotificationRead = async (id:string) => { await api.readNotification(id); setNotifications((current)=>({items:current.items.map((item)=>item.id===id?{...item,isRead:true}:item),unread:Math.max(0,current.unread-1)})) };
  const markAllNotificationsRead = async () => { await api.readAllNotifications(); setNotifications((current)=>({items:current.items.map((item)=>({...item,isRead:true})),unread:0})) };
  const navigate = (target: AppRoute) => runPageTransition(() => { setActive(target); setSelected(null); writeRoute(target); setQuery(''); setFilters(resetAllFilters()) });
  const mode = selected ? 'Candidate Dossiers' : active;
  const openCandidate = (id: string) => runPageTransition(() => { setActive('Candidate Dossiers'); setSelected(id); writeRoute('Candidate Dossiers', id) });
  const closeCandidate = () => runPageTransition(() => { setSelected(null); writeRoute('Candidate Dossiers') });
  const moveCandidate = (direction: number) => { const index = state.candidates.findIndex((candidate) => candidate.id === selected); const next = (index + direction + state.candidates.length) % state.candidates.length; const id = state.candidates[next]?.id ?? null; runPageTransition(() => { setSelected(id); writeRoute('Candidate Dossiers', id) }) };
  const selectedCandidate = selected ? state.candidates.find((candidate) => candidate.id === selected) : undefined;
  const toggleSidebar = () => { if (window.matchMedia('(max-width: 900px)').matches) { setMobileSidebarOpen((value) => !value); return } setSidebarCollapsed((value) => { const next = !value; localStorage.setItem('ceomentality:sidebar', next ? 'collapsed' : 'open'); return next }) };
  const hasSidebar = active !== 'Profile' && active !== 'Blacklist' && active !== 'Orders' && active !== 'Email' && active !== 'Team';
  const changeLanguage=(next:Language)=>{setRuntimeLanguage(next);setLanguage(next)};

  return <>
    <Header
      active={mode}
      navigate={navigate}
      candidates={state.candidates}
      user={currentUser}
      notifications={notifications}
      markNotificationRead={markNotificationRead}
      markAllNotificationsRead={markAllNotificationsRead}
      openCandidate={openCandidate}
      openProfile={() => navigate('Profile')}
      onLogout={logout}
      language={language}
      setLanguage={changeLanguage}
      hasSidebar={hasSidebar}
      desktopSidebarOpen={!sidebarCollapsed}
      mobileSidebarOpen={mobileSidebarOpen}
      toggleSidebar={toggleSidebar}
    />
    <div className={`app-shell ${!hasSidebar ? 'profile-shell' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${mobileSidebarOpen ? 'mobile-sidebar-open' : ''}`}>
      {hasSidebar && <>
        <Sidebar mode={mode} query={query} setQuery={setQuery} filters={filters} setFilters={setFilters} candidates={state.candidates} drops={state.drops} onClose={() => setMobileSidebarOpen(false)} reset={() => { setQuery(''); setFilters(resetAllFilters()) }} />
        <span className="sidebar-reveal-zone" />
        <button className="sidebar-toggle" onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Show filters' : 'Hide filters'}><Icon name="sidebar" size={20} /></button>
        <button className="mobile-sidebar-scrim" aria-label="Close filters" onClick={() => setMobileSidebarOpen(false)} />
      </>}
      {active === 'Profile' ? <ProfilePage notify={notify} onBack={() => navigate('Candidate Dossiers')} language={language} setLanguage={changeLanguage} />
        : active === 'Team' ? <TeamPage currentUser={currentUser} notify={notify} />
        : active === 'Blacklist' ? <BlacklistPage entries={blacklist} addEntry={addBlacklistEntry} removeEntry={removeBlacklistEntry} language={language} />
        : active === 'Email' ? <EmailPage drops={state.drops} notify={notify} />
        : active === 'Orders' ? <OrdersPage orders={orders} refund={refundOrder} complete={completeOrder} createShipment={createShipment} refreshShipment={refreshShipment} deleteOrder={deleteOrder} />
        : selectedCandidate ? <Dossier
            candidate={selectedCandidate}
            drops={state.drops}
            back={closeCandidate}
            update={updateCandidate}
            decide={(status) => decideCandidate(selectedCandidate.id, status)}
            assignCode={() => assignCandidateCode(selectedCandidate.id)}
            updatePurchase={(confirmed, product) => updatePurchase(selectedCandidate.id, confirmed, product)}
            updateMembership={(added) => updateMembership(selectedCandidate.id, added)}
            assignDrop={(wave) => assignCandidateDrop(selectedCandidate.id, wave)}
            addNote={(note) => addCandidateNote(selectedCandidate.id, note)}
            notify={notify}
            onPrevious={() => moveCandidate(-1)}
            onNext={() => moveCandidate(1)}
          />
        : active === 'Candidate Dossiers' ? <Dossiers candidates={state.candidates} open={openCandidate} query={query} filters={filters} />
        : active === 'Access Codes' ? <Access drops={state.drops} activity={state.activity} query={query} filters={filters} notify={notify} createDrop={() => setModal('drop')} generateBatch={generateBatch} regenerateDropCode={regenerateDropCode} resetFilters={() => { setQuery(''); setFilters(resetAllFilters()) }} activateDrop={activateDrop} closeDrop={closeDrop} deleteDrop={deleteDrop} issueDropCodes={issueDropCodes} exportData={exportData} />
        : <Analytics candidates={state.candidates} drops={state.drops} filters={filters} exportData={exportData} />}
    </div>
    {modal === 'candidate' && <CandidateForm onClose={() => setModal(null)} onSubmit={addCandidate} />}
    {modal === 'drop' && <DropForm onClose={() => setModal(null)} onSubmit={addDrop} />}
    {toast && <div className="toast">{toast}</div>}
  </>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');
createRoot(root).render(<ErrorBoundary><App /></ErrorBoundary>);
