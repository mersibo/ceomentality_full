import { useMemo, useState, type FormEvent } from 'react';
import { Icon } from '../../components/ui/Icon';
import { Modal } from '../../components/ui/Modal';
import type { BlacklistDraft, BlacklistEntry, Language } from '../../types/domain';

interface BlacklistPageProps {
  entries: BlacklistEntry[];
  addEntry: (draft: BlacklistDraft) => Promise<void>;
  removeEntry: (id: string) => Promise<void>;
  language: Language;
}

const emptyDraft: BlacklistDraft = { name: '', telegramId: '', telegramUsername: '', email: '', phone: '', reason: '' };

export function BlacklistPage({ entries, addEntry, removeEntry, language }: BlacklistPageProps) {
  const [query, setQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [draft, setDraft] = useState<BlacklistDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return entries;
    return entries.filter((entry) => [entry.name, entry.telegramId, entry.telegramUsername, entry.email, entry.phone, entry.reason].filter(Boolean).join(' ').toLowerCase().includes(needle));
  }, [entries, query]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (![draft.telegramId, draft.telegramUsername, draft.email, draft.phone].some(value => value?.trim())) return;
    setSaving(true);
    try {
      const telegramId = draft.telegramId?.trim();
      const telegramUsername = draft.telegramUsername?.trim();
      const email = draft.email?.trim();
      const phone = draft.phone?.trim();
      await addEntry({
        name: draft.name.trim(),
        ...(telegramId ? { telegramId } : {}),
        ...(telegramUsername ? { telegramUsername } : {}),
        ...(email ? { email } : {}),
        ...(phone ? { phone } : {}),
        reason: draft.reason.trim(),
      });
      setDraft(emptyDraft);
      setModalOpen(false);
    } catch {
      return;
    } finally {
      setSaving(false);
    }
  };

  return <main className="content blacklist-page">
    <div className="page-title-row">
      <div><div className="pretitle">Access control</div><h1>blacklist</h1><p>Blocked users cannot submit product or club applications.</p></div>
      <button className="primary-btn" onClick={() => setModalOpen(true)}><Icon name="plus" />Add person</button>
    </div>
    <div className="blacklist-toolbar">
      <label className="search-box"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, contacts or reason..." /></label>
      <span>{visible.length} active entries</span>
    </div>
    <section className="blacklist-table-wrap">
      <table className="blacklist-table">
        <thead><tr><th>Person</th><th>Contacts</th><th>Reason</th><th>Added</th><th aria-label="Actions" /></tr></thead>
        <tbody>{visible.map((entry) => <tr key={entry.id}>
          <td><strong>{entry.name || 'Unnamed user'}</strong></td>
          <td><span>{entry.telegramUsername ? `@${entry.telegramUsername}` : entry.email || 'No username or email'}</span><small>{entry.telegramId ? `ID ${entry.telegramId}` : entry.phone || 'No Telegram ID or phone'}</small></td>
          <td>{entry.reason}</td>
          <td>{new Date(entry.createdAt).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}</td>
          <td><button className="blacklist-remove" onClick={() => removeEntry(entry.id)} title="Remove from blacklist" aria-label="Remove from blacklist"><Icon name="x" size={16} /></button></td>
        </tr>)}</tbody>
      </table>
      {!visible.length && <div className="blacklist-empty">No blacklist entries found.</div>}
    </section>
    {modalOpen && <Modal title="Add to blacklist" onClose={() => setModalOpen(false)}><form className="form-grid" onSubmit={submit}>
      <label>Name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="Full name" /></label>
      <label>Telegram username<input value={draft.telegramUsername} onChange={(event) => setDraft({ ...draft, telegramUsername: event.target.value })} placeholder="@username" /></label>
      <label>Telegram ID<input value={draft.telegramId} onChange={(event) => setDraft({ ...draft, telegramId: event.target.value })} inputMode="numeric" placeholder="Numeric Telegram user ID" /></label>
      <label>Email<input type="email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} placeholder="user@example.com" /></label>
      <label className="full">Phone<input value={draft.phone} onChange={(event) => setDraft({ ...draft, phone: event.target.value })} inputMode="tel" placeholder="+79001234567" /></label>
      <label className="full">Reason<textarea required value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} placeholder="Reason shown to this user" /></label>
      <div className="form-actions"><button type="button" className="outline-btn" onClick={() => setModalOpen(false)}>Cancel</button><button className="primary-btn" disabled={saving || ![draft.telegramId, draft.telegramUsername, draft.email, draft.phone].some(value => value?.trim())}>{saving ? 'Adding...' : 'Add to blacklist'}</button></div>
    </form></Modal>}
  </main>;
}
