// Keep in sync with the CSS motion tokens. Seconds for Motion, ms in CSS.
export const duration = { fast: .15, normal: .25, reveal: .4, opening: .6 };
export const ease = [.22, 1, .36, 1] as const;
export const spring = { type: 'spring', stiffness: 320, damping: 32, mass: .8 } as const;

export const editorial = { tilt:2, magnetic:6, stagger:100, faqMaxMs:400 };
