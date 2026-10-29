"use client";
import Script from 'next/script';
import {useEffect} from 'react';
import {usePathname} from 'next/navigation';
export default function Tracker(){const path=usePathname();useEffect(()=>{window.dispatchEvent(new Event('hub:navigate'));},[path]);return <Script src="/t.js" strategy="afterInteractive"/>;}
