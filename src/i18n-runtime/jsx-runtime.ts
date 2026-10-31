import { Fragment, jsx as reactJsx, jsxs as reactJsxs } from 'react/jsx-runtime';
import { translateProps } from './shared';

export { Fragment };
export type { JSX } from 'react';
export const jsx=(...args:Parameters<typeof reactJsx>):ReturnType<typeof reactJsx>=>reactJsx(args[0],translateProps(args[1]),args[2]);
export const jsxs=(...args:Parameters<typeof reactJsxs>):ReturnType<typeof reactJsxs>=>reactJsxs(args[0],translateProps(args[1]),args[2]);
