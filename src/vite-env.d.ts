/// <reference types="vite/client" />

interface ViewTransition {
  finished:Promise<void>;
  ready:Promise<void>;
  updateCallbackDone:Promise<void>;
  skipTransition():void;
}

interface Document {
  startViewTransition?(update:()=>void|Promise<void>):ViewTransition;
}
