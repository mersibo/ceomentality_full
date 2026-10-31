import type { ReactNode } from 'react';

export type IconName = 'search'|'bell'|'plus'|'download'|'arrow'|'calendar'|'left'|'check'|'x'|'link'|'bookmark'|'users'|'trend'|'target'|'copy'|'sidebar'|'more'|'grid'|'list'|'minus'|'lock';

interface IconProps { name: IconName; size?: number }

const paths: Record<IconName, ReactNode> = {
  search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>, bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M10 19a2 2 0 0 0 4 0"/></>,
  plus:<path d="M12 5v14M5 12h14"/>, download:<><path d="M12 3v12"/><path d="m7 10 5 5 5-5M5 21h14"/></>, arrow:<><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>, calendar:<><rect x="3.5" y="5.5" width="17" height="15" rx="2"/><path d="M7.5 3.5v4M16.5 3.5v4M3.5 10h17"/><path d="M8 14h2M14 14h2M8 17.5h2M14 17.5h2"/></>,
  left:<><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></>, check:<path d="m5 13 4 4L19 7"/>, x:<path d="M18 6 6 18M6 6l12 12"/>, link:<><path d="M10 13a5 5 0 0 0 7 .2l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7-.2l-2 2a5 5 0 0 0 7 7l1-1"/></>, bookmark:<path d="M6 4h12v17l-6-4-6 4z"/>, users:<><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>, trend:<path d="m4 16 5-5 4 4 7-8M15 7h5v5"/>, target:<><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></>, copy:<><rect x="9" y="9" width="10" height="10" rx="2"/><rect x="5" y="5" width="10" height="10" rx="2"/></>, sidebar:<><rect x="3" y="4" width="18" height="16" rx="4"/><path d="M9 4v16"/></>,
  more:<><circle cx="5" cy="12" r="1.35" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.35" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.35" fill="currentColor" stroke="none"/></>, grid:<><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></>, list:<><path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="18" r="1" fill="currentColor" stroke="none"/></>, minus:<path d="M5 12h14"/>, lock:<><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>
};

export function Icon({name,size=18}:IconProps) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
