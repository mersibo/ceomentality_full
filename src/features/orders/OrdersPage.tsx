import { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import type { StoreOrder } from '../../types/domain';

interface OrdersPageProps {
  orders: StoreOrder[];
  refund: (id:string) => Promise<void>;
  complete: (id:string) => Promise<void>;
  createShipment: (id:string) => Promise<void>;
  refreshShipment: (id:string) => Promise<void>;
  deleteOrder: (id:string) => Promise<void>;
}

const money = (kopecks:number) => new Intl.NumberFormat('ru-RU', {
  style:'currency', currency:'RUB', maximumFractionDigits:0,
}).format(kopecks / 100);

export function OrdersPage({orders,refund,complete,createShipment,refreshShipment,deleteOrder}:OrdersPageProps) {
  const [selected,setSelected]=useState<{order:StoreOrder;action:'refund'|'complete'|'shipment'|'delete'}|null>(null);
  const [busy,setBusy]=useState(false);
  const refresh=async(order:StoreOrder)=>{setBusy(true);try{await refreshShipment(order.id)}finally{setBusy(false)}};
  const confirm=async()=>{
    if(!selected)return;
    setBusy(true);
    try {
      await (selected.action==='refund' ? refund(selected.order.id) : selected.action==='shipment' ? createShipment(selected.order.id) : selected.action==='delete' ? deleteOrder(selected.order.id) : complete(selected.order.id));
      setSelected(null);
    }
    finally { setBusy(false) }
  };
  return <main className="content orders-page">
    <div className="page-head"><div><div className="pretitle">Store orders</div><h1>Orders</h1><p>Payments, delivery charges and refunds.</p></div></div>
    <section className="panel orders-table-wrap">
      {orders.length?<table className="orders-table"><thead><tr><th>Order</th><th>Customer</th><th>Payment</th><th>Total</th><th/></tr></thead><tbody>{orders.map(order=><tr key={order.id}>
        <td><strong>{order.id}</strong><small>{new Date(order.createdAt).toLocaleString('ru-RU')}</small></td>
        <td><strong>{order.customer.name||'—'}</strong><small>{order.customer.email||order.customer.phone||'—'}</small><small>{order.customer.address||'—'}</small></td>
        <td><span className={`order-status status-${order.status}`}>{order.status.replaceAll('_',' ')}</span><small>{order.tracking?.number||order.tracking?.uuid||order.payment?.providerPaymentId||'—'}</small></td>
        <td><strong>{money(order.total)}</strong><small>Delivery: {money(order.delivery)}</small></td>
        <td><div className="order-actions">{['paid','shipped','delivered'].includes(order.status)&&order.payment?.provider==='tbank'?<>{order.status==='paid'&&!order.tracking?.uuid?<button className="primary-btn small" onClick={()=>setSelected({order,action:'shipment'})}>Create CDEK shipment</button>:null}{order.tracking?.uuid?<button className="outline-btn small" disabled={busy} onClick={()=>void refresh(order)}>Refresh CDEK</button>:null}{['paid','shipped'].includes(order.status)?<button className="outline-btn small" onClick={()=>setSelected({order,action:'complete'})}>Mark delivered</button>:null}<button className="outline-btn small" onClick={()=>setSelected({order,action:'refund'})}>Refund</button></>:null}{!['paid','shipped','delivered'].includes(order.status)&&<button className="outline-btn small danger" onClick={()=>setSelected({order,action:'delete'})}>Delete</button>}</div></td>
      </tr>)}</tbody></table>:<div className="orders-empty">No store orders yet</div>}
    </section>
    {selected&&<Modal title={selected.action==='refund'?'Issue full refund':selected.action==='shipment'?'Create CDEK shipment':selected.action==='delete'?'Delete order':'Mark order delivered'} onClose={()=>!busy&&setSelected(null)}><div className="refund-copy"><p>{selected.action==='refund'?'This action sends a full refund request to T-Bank. The operation cannot be undone in CRM.':selected.action==='shipment'?'CRM will create a paid CDEK shipment to the pickup point selected by the buyer.':selected.action==='delete'?'The order and its payment records will be permanently removed from CRM.':'Confirm that the product was handed to the buyer. CRM will send the closing receipt to T-Bank.'}</p><strong>{selected.order.id} · {money(selected.order.total)}</strong></div><div className="settings-actions"><button className="outline-btn" disabled={busy} onClick={()=>setSelected(null)}>Cancel</button><button className="primary-btn" disabled={busy} onClick={()=>void confirm()}>{busy?'Processing...':selected.action==='refund'?'Confirm refund':selected.action==='shipment'?'Create shipment':selected.action==='delete'?'Delete order':'Confirm delivery'}</button></div></Modal>}
  </main>;
}
