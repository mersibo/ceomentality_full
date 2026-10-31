import { Fragment, jsxDEV as reactJsxDEV } from 'react/jsx-dev-runtime';
import { translateProps } from './shared';

export { Fragment };
export type { JSX } from 'react';
export const jsxDEV=(...args:Parameters<typeof reactJsxDEV>):ReturnType<typeof reactJsxDEV>=>reactJsxDEV(args[0],translateProps(args[1]),args[2],args[3],args[4],args[5]);
