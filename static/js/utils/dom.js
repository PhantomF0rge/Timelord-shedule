export const $ = (sel, root=document) => root.querySelector(sel);
export const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
export const show = (el) => el && (el.hidden = false);
export const hide = (el) => el && (el.hidden = true);
