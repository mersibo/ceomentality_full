import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { AccessBatch, EmailCampaign, EmailCampaignPreview, EmailSettings } from '../../types/domain';

interface EmailPageProps {
  drops: AccessBatch[];
  notify: (message:string)=>void;
}

const defaultSubject='Ваш код доступа к дропу {{drop_name}}';
const defaultBody=[
  'Здравствуйте, {{name}}!',
  '',
  'Ваша заявка на участие в дропе «{{drop_name}}» одобрена.',
  '',
  'Код доступа: {{drop_code}}',
  'Срок действия: {{validity}}',
  '',
  'CEOMENTALITY',
].join('\n');

export function EmailPage({drops,notify}:EmailPageProps) {
  const [settings,setSettings]=useState<EmailSettings|null>(null);
  const [campaigns,setCampaigns]=useState<EmailCampaign[]>([]);
  const [dropId,setDropId]=useState('');
  const [subject,setSubject]=useState(defaultSubject);
  const [body,setBody]=useState(defaultBody);
  const [preview,setPreview]=useState<EmailCampaignPreview|null>(null);
  const [busy,setBusy]=useState(false);
  const activeDrops=drops.filter(drop=>drop.status==='Active');

  const reload=async()=>{
    const [nextSettings,nextCampaigns]=await Promise.all([api.emailSettings(),api.listEmailCampaigns()]);
    setSettings(nextSettings);setCampaigns(nextCampaigns);
    if(!dropId&&activeDrops[0])setDropId(activeDrops[0].id);
  };
  useEffect(()=>{void reload().catch(error=>notify(error instanceof Error?error.message:'Не удалось загрузить email-рассылки'))},[]);
  useEffect(()=>{setPreview(null)},[dropId]);

  const saveSettings=async()=>{
    if(!settings)return;
    setBusy(true);
    try{
      setSettings(await api.updateEmailSettings({
        fromEmail:settings.fromEmail,
        fromName:settings.fromName,
        sendingKeyId:settings.sendingKeyId,
      }));
      notify('Настройки отправителя сохранены');
    }catch(error){notify(error instanceof Error?error.message:'Не удалось сохранить настройки')}
    finally{setBusy(false)}
  };
  const loadPreview=async()=>{
    if(!dropId)return;
    setBusy(true);
    try{setPreview(await api.previewEmailCampaign(dropId))}
    catch(error){notify(error instanceof Error?error.message:'Не удалось получить получателей')}
    finally{setBusy(false)}
  };
  const send=async()=>{
    if(!dropId||!subject.trim()||!body.trim()||!preview?.deliverable)return;
    setBusy(true);
    try{
      const campaign=await api.createEmailCampaign({dropId,subject,body});
      setCampaigns(current=>[campaign,...current]);
      setPreview(null);
      notify('Email-рассылка поставлена в очередь: '+campaign.recipientCount);
    }catch(error){notify(error instanceof Error?error.message:'Не удалось создать рассылку')}
    finally{setBusy(false)}
  };

  return <main className="content email-page">
    <div className="page-head"><div><div className="pretitle">RuSender</div><h1>Email-рассылки</h1><p>Отдельный канал для писем участникам дропов.</p></div></div>
    {!settings?.providerConfigured&&<div className="form-alert">RuSender пока не подключён. Добавьте API-токен в серверный файл окружения.</div>}
    <section className="email-layout">
      <div className="email-main">
        <section className="panel email-editor">
          <div className="section-title"><div><span>Новое письмо</span><h2>Содержание рассылки</h2></div></div>
          <label className="settings-field"><span>Дроп</span><select value={dropId} onChange={event=>setDropId(event.target.value)}><option value="">Выберите активный дроп</option>{activeDrops.map(drop=><option key={drop.id} value={drop.id}>{drop.name}</option>)}</select></label>
          <label className="settings-field"><span>Тема письма</span><input maxLength={255} value={subject} onChange={event=>setSubject(event.target.value)}/></label>
          <label className="settings-field"><span>Текст письма</span><textarea rows={12} maxLength={20000} value={body} onChange={event=>setBody(event.target.value)}/></label>
          <p className="email-variables">Переменные: <code>{'{{name}}'}</code> <code>{'{{drop_name}}'}</code> <code>{'{{drop_code}}'}</code> <code>{'{{validity}}'}</code></p>
          <div className="settings-actions"><button className="outline-btn" disabled={busy||!dropId} onClick={()=>void loadPreview()}>Проверить получателей</button><button className="primary-btn" disabled={busy||!settings?.providerConfigured||!preview?.deliverable||!subject.trim()||!body.trim()} onClick={()=>void send()}>Поставить в очередь</button></div>
        </section>
        {preview&&<section className="panel email-recipients"><div className="section-title"><div><span>Выбрали получение по email</span><h2>{preview.dropName}</h2></div><strong>{preview.deliverable} получателей</strong></div><div className="settings-list">{preview.recipients.map(item=><div key={item.candidateId}><span><b>{item.name}</b><small>{item.email||'Email не указан'}</small></span><strong>{item.deliverable?'Готово':'Пропущен'}</strong></div>)}{!preview.recipients.length&&<div className="search-empty">Нет одобренных участников с выбранной доставкой по email</div>}</div>{preview.missingEmail>0&&<p className="small-note">Без email: {preview.missingEmail}. Эти пользователи не попадут в очередь.</p>}</section>}
      </div>
      <aside className="panel email-sender">
        <div className="section-title"><div><span>Отправитель</span><h2>Настройки</h2></div></div>
        {settings&&<><label className="settings-field"><span>Имя</span><input value={settings.fromName} onChange={event=>setSettings({...settings,fromName:event.target.value})}/></label><label className="settings-field"><span>Email</span><input type="email" value={settings.fromEmail} onChange={event=>setSettings({...settings,fromEmail:event.target.value})}/></label><label className="settings-field"><span>Key ID, необязательно</span><input inputMode="numeric" placeholder="Определится автоматически" value={settings.sendingKeyId??''} onChange={event=>setSettings({...settings,sendingKeyId:event.target.value?Number(event.target.value):null})}/></label><button className="primary-btn" disabled={busy||!settings.fromName.trim()||!settings.fromEmail.trim()} onClick={()=>void saveSettings()}>Сохранить отправителя</button></>}
      </aside>
    </section>
    <section className="panel email-history">
      <div className="section-title"><div><span>История</span><h2>Последние рассылки</h2></div><button className="outline-btn small" onClick={()=>void reload()}>Обновить</button></div>
      {campaigns.length?<table className="orders-table"><thead><tr><th>Дата</th><th>Дроп и тема</th><th>Статус</th><th>Результат</th></tr></thead><tbody>{campaigns.map(item=><tr key={item.id}><td>{new Date(item.createdAt).toLocaleString('ru-RU')}</td><td><strong>{item.dropName}</strong><small>{item.subject}</small></td><td><span className={'order-status status-'+item.status}>{item.status.replaceAll('_',' ')}</span></td><td><strong>{item.sentCount} / {item.recipientCount}</strong><small>{item.failedCount?'Ошибок: '+item.failedCount:'Без ошибок'}</small></td></tr>)}</tbody></table>:<div className="orders-empty">Рассылок пока нет</div>}
    </section>
  </main>;
}
