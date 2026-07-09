"""Reusable UI component library — the orchestrator's stored design patterns.

A curated set of high-craft, copy-and-adapt HTML/CSS/JS snippets the CoderAgent
assembles a UI from, instead of inventing every component from scratch. Models
(especially smaller/cheaper ones) produce far better, more consistent UIs when
given concrete building blocks to lift and restyle.

Patterns distilled from current high-end web design (motionsites.ai showcase,
Awwwards/Mobbin, Stripe/Linear/Vercel/Apple) and 2026 trends: design tokens,
sticky glass nav, expressive heroes, bento grids, glassmorphism cards, scroll-
reveal motion, marquees, count-up stats, testimonials, CTA bands, footers.

The coder MUST adapt these to the project's brand (colors, fonts, copy, imagery)
— they are scaffolding to reach the quality bar, not a fixed theme to ship as-is.
"""
from __future__ import annotations

COMPONENT_LIBRARY = r"""
## Component library (assemble + RESTYLE these — don't ship them verbatim)

These are reference patterns. Lift the structure, then rebrand: swap colors,
fonts, radii, copy and imagery to fit the product. A finished page weaves
several of these together with a cohesive token system.

### 1. Design tokens (define once in :root, reuse everywhere)
```css
:root{
  --bg:#0b0b0f; --surface:#15151c; --ink:#ececf1; --muted:#9aa0ad;
  --accent:#7c5cff; --accent-2:#22d3ee; --line:rgba(255,255,255,.08);
  --radius:16px; --shadow:0 24px 60px -24px rgba(0,0,0,.6);
  --space:clamp(4rem,8vw,7rem); --maxw:1180px;
  --font-display:'Fraunces',Georgia,serif; --font-body:'Inter',system-ui,sans-serif;
}
*{box-sizing:border-box;margin:0} html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font-family:var(--font-body);line-height:1.6}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 1.5rem}
.eyebrow{font-size:.72rem;letter-spacing:.28em;text-transform:uppercase;color:var(--accent)}
h1,h2,h3{font-family:var(--font-display);font-weight:600;line-height:1.05;letter-spacing:-.02em}
```

### 2. Sticky glassmorphism nav (frosts on scroll)
```html
<nav id="nav" class="nav"><div class="wrap nav-in">
  <a class="brand">◆ Brand</a>
  <div class="links"><a href="#features">Features</a><a href="#pricing">Pricing</a></div>
  <a class="btn">Get started</a>
</div></nav>
```
```css
.nav{position:sticky;top:0;z-index:50;transition:.3s;border-bottom:1px solid transparent}
.nav.solid{background:color-mix(in srgb,var(--bg) 72%,transparent);backdrop-filter:blur(14px);border-color:var(--line)}
.nav-in{display:flex;align-items:center;justify-content:space-between;height:72px}
.links{display:flex;gap:2rem}.links a{color:var(--muted);text-decoration:none}.links a:hover{color:var(--ink)}
@media(max-width:760px){.links{display:none}}
```

### 3. Hero with gradient mesh + entrance animation
```html
<header class="hero"><span class="mesh"></span><div class="wrap hero-in">
  <span class="eyebrow">Eyebrow label</span>
  <h1>A bold headline that<br><em>carries</em> the design.</h1>
  <p class="lead">One clear sentence of supporting value proposition.</p>
  <div class="cta"><a class="btn">Primary action →</a><a class="btn ghost">Secondary</a></div>
</div></header>
```
```css
.hero{position:relative;padding:var(--space) 0;overflow:hidden}
.mesh{position:absolute;inset:-20% -10% auto;height:520px;filter:blur(80px);opacity:.5;z-index:0;
  background:radial-gradient(40% 60% at 30% 30%,var(--accent),transparent),radial-gradient(40% 60% at 70% 40%,var(--accent-2),transparent)}
.hero-in{position:relative;z-index:1;max-width:46rem}
.hero h1{font-size:clamp(2.6rem,7vw,5rem);font-weight:500;margin:1rem 0}
.hero h1 em{font-style:italic;color:var(--accent)}
.lead{font-size:1.15rem;color:var(--muted);max-width:34rem;margin-bottom:2rem}
.cta{display:flex;gap:.8rem;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.9rem 1.6rem;border-radius:999px;text-decoration:none;
  font-weight:600;background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;box-shadow:var(--shadow);transition:transform .15s}
.btn:hover{transform:translateY(-2px)} .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--ink);box-shadow:none}
.hero-in>*{opacity:0;transform:translateY(20px);animation:rise .8s ease forwards}
.hero-in>*:nth-child(2){animation-delay:.08s}.hero-in>*:nth-child(3){animation-delay:.16s}.hero-in>*:nth-child(4){animation-delay:.24s}
@keyframes rise{to{opacity:1;transform:none}}
```

### 4. Bento grid (mixed-size feature cells = instant hierarchy)
```css
.bento{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}
.cell{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:1.6rem;transition:transform .2s,border-color .2s}
.cell:hover{transform:translateY(-4px);border-color:color-mix(in srgb,var(--accent) 50%,var(--line))}
.cell.lg{grid-column:span 2;grid-row:span 2} .cell.wide{grid-column:span 2}
@media(max-width:760px){.bento{grid-template-columns:1fr}.cell.lg,.cell.wide{grid-column:auto}}
```

### 5. Glassmorphism card (pricing / product) over a colorful backdrop
```css
.glass{background:rgba(255,255,255,.06);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.12);
  border-radius:var(--radius);padding:1.8rem;box-shadow:var(--shadow)}
.glass.featured{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent),var(--shadow)}
.price{font-family:var(--font-display);font-size:2.6rem} .price span{font-size:1rem;color:var(--muted)}
```

### 6. Section heading + scroll-reveal wrapper
```html
<section class="sec" id="features"><div class="wrap">
  <div class="head reveal"><span class="eyebrow">Eyebrow</span><h2>Section title</h2></div>
  <!-- grid of .cell / .glass here, each with class="reveal" -->
</div></section>
```
```css
.sec{padding:var(--space) 0}.head{text-align:center;max-width:40rem;margin:0 auto 3rem}
.head h2{font-size:clamp(2rem,4vw,3rem)}
.reveal{opacity:0;transform:translateY(28px);transition:opacity .7s ease,transform .7s ease}
.reveal.in{opacity:1;transform:none}
```

### 7. Count-up stats band
```html
<div class="stats"><div class="stat"><b data-count="12000">0</b><span>Customers</span></div>…</div>
```
```js
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){const el=e.target,t=+el.dataset.count,s=performance.now();
 (function f(n){const p=Math.min((n-s)/1400,1);el.textContent=Math.round(t*(1-Math.pow(1-p,3))).toLocaleString();p<1&&requestAnimationFrame(f);})(s);io.unobserve(el);}}),{threshold:.6});
document.querySelectorAll('[data-count]').forEach(el=>io.observe(el));
```

### 8. Infinite marquee (logos / announcements)
```css
.marquee{overflow:hidden;white-space:nowrap}.marquee>div{display:inline-block;animation:scroll 24s linear infinite}
@keyframes scroll{to{transform:translateX(-50%)}}  /* duplicate the content twice inside >div */
```

### 9. Testimonials (centered serif quotes)
```css
.tcard{text-align:center;padding:1.5rem}.tcard p{font-family:var(--font-display);font-style:italic;font-size:1.3rem;color:var(--ink)}
.tcard .who{display:flex;gap:.6rem;align-items:center;justify-content:center;margin-top:1rem;color:var(--muted)}
.tcard img{width:42px;height:42px;border-radius:50%}
```

### 10. CTA band + footer
```css
.cta-band{margin:0 auto;max-width:var(--maxw);border-radius:28px;padding:var(--space) 1.5rem;text-align:center;
  background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff}
footer{border-top:1px solid var(--line);padding:3rem 0;color:var(--muted)}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:2rem}
```

### 11. Required motion + interaction JS (include near </body>)
```js
// nav frosts on scroll
addEventListener('scroll',()=>document.getElementById('nav')?.classList.toggle('solid',scrollY>20));
// scroll-reveal (respect reduced motion)
const rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
if(rm){document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'));}
else{const ro=new IntersectionObserver(es=>es.forEach(e=>e.isIntersecting&&e.target.classList.add('in')),{threshold:.14});
 document.querySelectorAll('.reveal').forEach(e=>ro.observe(e));}
```

### Imagery & icons
- Photos: `https://images.unsplash.com/photo-<id>?auto=format&fit=crop&w=900&q=80` with an `onerror` gradient/emoji fallback so it never looks broken.
- Avatars: `https://i.pravatar.cc/80?img=<n>`. Icons: inline SVG or emoji.
"""


PREMIUM_PATTERNS = r"""
## Premium / cinematic patterns (the high-end tier — use these to feel "designed")

These are the techniques behind award-grade pages. Use them tastefully; adapt
colors/copy/fonts to the brand. They work in vanilla HTML/CSS/JS; the React +
Framer Motion equivalents are noted where relevant.

### A. Fullscreen looping video background (instant cinematic depth)
```html
<video autoplay muted loop playsinline class="bg-video"
       poster="<fallback-image>"><source src="<VIDEO_URL>.mp4" type="video/mp4"></video>
<div class="v-overlay"></div>  <!-- gradient/scrim so text stays legible -->
<main class="content"><!-- z-10 content --></main>
```
```css
.bg-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-0}
.v-overlay{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.35),transparent 40%,rgba(0,0,0,.65))}
.content{position:relative;z-index:10}
```
Let the video carry the visuals — keep the layout minimal and vertically centered.

### B. Liquid glass / glassmorphism button & panel (use over video/gradients)
```css
.liquid-glass{position:relative;overflow:hidden;border:none;border-radius:999px;
  background:rgba(255,255,255,.06);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,.18);transition:transform .2s}
.liquid-glass:hover{transform:scale(1.03)}
.liquid-glass::before{content:"";position:absolute;inset:0;border-radius:inherit;padding:1.4px;pointer-events:none;
  background:linear-gradient(180deg,rgba(255,255,255,.45),rgba(255,255,255,.1) 30%,transparent 50%,rgba(255,255,255,.1) 70%,rgba(255,255,255,.45));
  -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);-webkit-mask-composite:xor;mask-composite:exclude}
```

### C. Cinematic typography
- Oversized fluid headings: `font-size:clamp(2.5rem,14vw,17rem);line-height:.9;letter-spacing:-.03em` (vw-based for hero drama).
- Gradient text: `background:linear-gradient(180deg,#646973,#BBCCD7);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent`.
- Serif-italic accent inside a sans heading for editorial contrast (e.g. Instrument Serif italic on one phrase).
- Pair a distinctive display font (Helvetica Now Display, Kanit, Almarai, Instrument Serif) with Inter for body. Load via Google Fonts / onlinewebfonts `<link>`.

### D. Entrance + scroll motion (vanilla CSS)
```css
@keyframes fade-rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
.fade-rise{animation:fade-rise .8s ease-out both}
.fade-rise.d1{animation-delay:.2s}.fade-rise.d2{animation-delay:.4s}.fade-rise.d3{animation-delay:.6s}
```
Stagger hero elements with `.d1/.d2/.d3`. Easings that feel premium: `cubic-bezier(.22,1,.36,1)` (out) and `cubic-bezier(.16,1,.3,1)`.

### E. Framer Motion recipes (when the project is React + framer-motion)
- Shared fade-up variant (stagger by index `i`):
  `hidden:{opacity:0,y:28}; visible:(i)=>({opacity:1,y:0,transition:{delay:i*0.15,duration:0.6,ease:[0.22,1,0.36,1]}})`
- WordsPullUp: split the heading on spaces; each word is a `motion.span` sliding `y:20→0`, staggered `delay:i*0.08`, fired by `useInView({once:true})`.
- AnimatedText (char-by-char scroll reveal): `useScroll({target:ref,offset:['start 0.8','end 0.2']})`; each char's opacity maps `0.2→1` over `[i/n - .1, i/n + .05]` via `useTransform`.
- Magnet (magnetic hover): track cursor vs element center; when within a padding radius apply `translate3d(dx/strength, dy/strength,0)`; `transition: transform .3s ease-out` in, `.6s ease-in-out` out; `will-change:transform`.
- Sticky-stacking cards: each card `sticky top-24` inside a tall section; `useScroll` + `useTransform` scale each to `1-(n-1-i)*0.03` as the next scrolls over it.
- Mobile menu: `AnimatePresence` with a fading backdrop (`rgba(...,.35)`,`backdrop-blur`) + a right slide-in sheet (`x:'100%'→0`, ease `[0.22,1,0.36,1]`, ~0.45s); nav links stagger in `x:24→0`.
- Scroll-driven marquee: rows of tiles translated by `scrollY`-derived offset (one row +x, one −x) for parallax movement.

### F. Premium buttons
```css
/* gradient pill */
.btn-grad{border:none;cursor:pointer;color:#fff;font-weight:600;text-transform:uppercase;letter-spacing:.1em;
  padding:1rem 1.5rem;border-radius:999px;background:linear-gradient(123deg,#18011F,#B600A8 37%,#7621B0 72%,#BE4C00);
  box-shadow:0 4px 24px rgba(181,1,167,.28);transition:transform .15s,filter .2s}
.btn-grad:hover{transform:scale(1.04);filter:brightness(1.1)} .btn-grad:active{transform:scale(.96)}
/* ghost / outline pill */
.btn-ghost{border:2px solid currentColor;background:transparent;border-radius:999px;padding:.8rem 1.5rem;
  text-transform:uppercase;letter-spacing:.1em;cursor:pointer;transition:background .2s}
.btn-ghost:hover{background:color-mix(in srgb,currentColor 12%,transparent)}
```

### G. Runnable React/Vite/Tailwind/Framer project (when you choose React)
If you build with React + Vite + TS + Tailwind + framer-motion + lucide-react, you
MUST emit the COMPLETE runnable set so `npm install && npm run dev` works:
`package.json` (deps: react, react-dom, framer-motion, lucide-react; devDeps: vite,
@vitejs/plugin-react, typescript, tailwindcss, postcss, autoprefixer),
`vite.config.ts`, `tailwind.config.js` (content globs), `postcss.config.js`,
`tsconfig.json`, `index.html` (font `<link>`s + `<div id="root">` + module script),
`src/main.tsx`, `src/App.tsx`, `src/index.css` (`@tailwind base/components/utilities`
+ `:root` tokens + custom utilities like `.liquid-glass`). A partial React app that
won't build is a FAILURE — if unsure, ship a single self-contained `index.html`
instead and translate these motion techniques to vanilla JS.

### H. More signature touches (from premium reference specs)
- Filmic noise grain over video/sections (subtle, premium):
```css
.noise{position:absolute;inset:0;pointer-events:none;opacity:.5;mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
```
- Nav pill that hangs from the top edge: `.nav-pill{background:#000;border-radius:0 0 1.5rem 1.5rem;padding:.5rem 2rem}` centered at top.
- Inline icons inside a heading (verticalAlign:middle; position:relative; top:-2px; margin:0 4px) for playful display headlines.
- Giant-number list rows (services/projects): a flex row with `font-size:clamp(3rem,10vw,140px)` index number + a stacked name (uppercase) and muted description; rows split by 1px hairline borders; stagger each in.
- Oversized vw display headings with gradient or two-tone color, `line-height:.85`, `letter-spacing:-.05em`, optional superscript `®`/`*` (`<sup>` or absolutely-positioned, `font-size:.3em`).
- Multi-style word pull-up: split a heading into words but give one phrase a serif-italic accent class (e.g. Instrument Serif italic) while the rest stay sans — words slide up `y:20→0` staggered.

A catalog of full premium reference specs lives in `reference_specs.py` for
distillation — adapt their *techniques*, never their brand names or content.
"""


FUNCTIONAL_PATTERNS = r"""
## Functional patterns (make the site actually WORK — wire these up)

A finished frontend is interactive. Include the behaviors the product implies;
here are the reusable recipes (vanilla JS shown — use React state equivalents in
a React project).

### Sticky nav: frost on scroll + active-section highlight + smooth scroll
```js
const nav=document.getElementById('nav');
addEventListener('scroll',()=>nav.classList.toggle('solid',scrollY>20));
const links=[...document.querySelectorAll('.nav-link')];
const obs=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)
  links.forEach(l=>l.classList.toggle('active',l.getAttribute('href')==='#'+e.target.id));
}),{rootMargin:'-45% 0px -50% 0px'});
document.querySelectorAll('section[id]').forEach(s=>obs.observe(s));
```
(Use `html{scroll-behavior:smooth;scroll-padding-top:<navHeight>}` for in-page links.)

### Mobile slide-in menu (hamburger → sheet + backdrop, closes on tap)
```js
const sheet=document.getElementById('sheet'),panel=document.getElementById('panel');
const open=()=>{sheet.classList.remove('hidden');requestAnimationFrame(()=>panel.classList.remove('translate-x-full'));};
const close=()=>{panel.classList.add('translate-x-full');setTimeout(()=>sheet.classList.add('hidden'),300);};
burger.onclick=open; sheet.querySelectorAll('[data-close]').forEach(x=>x.onclick=close);
```

### Filter / tabs (actually filters a rendered list)
```js
const render=(f='all')=>grid.innerHTML=DATA.filter(d=>f==='all'||d.cat===f).map(cardHTML).join('');
render();
filters.forEach(b=>b.onclick=()=>{filters.forEach(x=>x.classList.remove('active'));b.classList.add('active');render(b.dataset.f);});
```

### Form with validation + success feedback (contact / sign-up / newsletter)
```js
form.addEventListener('submit',e=>{e.preventDefault();
  const f=new FormData(form),name=(f.get('name')||'').trim(),email=(f.get('email')||'').trim();
  const okEmail=/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  if(!name||!okEmail){note.textContent='Please add your name and a valid email.';note.dataset.err=1;return;}
  note.removeAttribute('data-err');note.textContent='Thanks — we\'ll be in touch shortly.';
  form.reset();toast('Sent ✓');                       // + show a toast
});
```

### Toast helper
```js
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');
  clearTimeout(window._t);window._t=setTimeout(()=>t.classList.remove('show'),2600);}
```

### Seed demo data so sections are populated
```js
const PRODUCTS=[{t:'Plan Pro',cat:'plan',price:29},/* … */];
const POSTS=[{t:'Title',cat:'Essay',img:'<unsplash-id>'},/* … */];
```
Always render real-looking items (names, prices, copy, images) — never "Item 1 / Item 2".
"""
