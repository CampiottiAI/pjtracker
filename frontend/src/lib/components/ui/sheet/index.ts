import { Dialog as SheetPrimitive } from 'bits-ui';

import Root from './sheet.svelte';
import Content from './sheet-content.svelte';
import Description from './sheet-description.svelte';
import Footer from './sheet-footer.svelte';
import Header from './sheet-header.svelte';
import Overlay from './sheet-overlay.svelte';
import Title from './sheet-title.svelte';

const Trigger = SheetPrimitive.Trigger;
const Close = SheetPrimitive.Close;
const Portal = SheetPrimitive.Portal;

export {
	Root,
	Content,
	Description,
	Footer,
	Header,
	Overlay,
	Title,
	Trigger,
	Close,
	Portal,
	Root as Sheet,
	Content as SheetContent,
	Description as SheetDescription,
	Footer as SheetFooter,
	Header as SheetHeader,
	Overlay as SheetOverlay,
	Title as SheetTitle,
	Trigger as SheetTrigger,
	Close as SheetClose,
	Portal as SheetPortal
};
