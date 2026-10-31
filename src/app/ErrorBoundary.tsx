import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props { children:ReactNode }
interface State { error:Error|null }

export class ErrorBoundary extends Component<Props,State> {
 state:State={error:null};
 static getDerivedStateFromError(error:Error):State { return {error} }
 componentDidCatch(error:Error,info:ErrorInfo):void { console.error('CEOMENTALITY UI error',error,info) }
 render():ReactNode {
  if(!this.state.error)return this.props.children;
  return <main className="loading" role="alert"><div><strong>Workspace could not be displayed.</strong><br/><button className="outline-btn" onClick={()=>window.location.reload()}>Reload workspace</button></div></main>;
 }
}
