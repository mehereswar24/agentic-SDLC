"""Reference design specs — a stored catalog of premium, fully-detailed frontend
prompts supplied as exemplars of the quality/precision bar to aim for.

These are kept as REFERENCE material (for distillation and future few-shot use),
NOT injected verbatim into every coder call — they are long and brand-specific,
and the coder must write content for the *requested* product, not copy these.
Their reusable techniques are distilled into `component_library.PREMIUM_PATTERNS`
and `FUNCTIONAL_PATTERNS`. Add new exemplars here as they come in.
"""
from __future__ import annotations

REFERENCE_SPECS: dict[str, str] = {
    "password-manager-hero": r"""
Password manager landing-page hero (React + TS + Tailwind + Framer Motion + Lucide).
- Fonts: heading "Helvetica Now Display Bold" via onlinewebfonts <link>; body Inter
  300-900 via Google Fonts @import in index.css.
- CSS vars in :root: --font-heading, --font-body, --color-text #192837,
  --color-accent #7342E2, --color-login-bg #F2F2EE. Global reset *{box-sizing:border-box}.
- Full-viewport looping background <video> (autoPlay muted loop playsInline,
  absolute inset-0 z-0 w-full h-full object-cover). URL: a CloudFront .mp4.
- Inline SVG geometric logo 32x32 viewBox 0 0 256 256 fill #192837.
- Navbar (max-w 1280px, px-5 sm:px-8 py-4 sm:py-5, relative z-10, justify-between):
  left logo; center md:flex links Vault/Plans/Install/News/Help (text-sm font-medium,
  hover:opacity-70, gap-8); right md:flex two pills gap-3 — "Start For Free" (#7342E2,
  white, px-5 py-2.5 rounded-full, hover shadow, active scale-95) and "Sign In"
  (#F2F2EE). Mobile md:hidden hamburger (Lucide Menu, toggles to X).
- Mobile menu via AnimatePresence: backdrop rgba(25,40,55,.35)+blur(4px) fade .3s;
  right sheet width min(88vw,360px) height 100dvh bg #CFC8C5 shadow -12px 0 48px,
  slide-in cubic-bezier [0.22,1,0.36,1] .45s, exit [0.55,0,1,0.45] .35s; header logo +
  circular close (40x40 rgba(25,40,55,.1), X 20px, whileTap scale .9); divider 1px
  rgba(25,40,55,.12); nav links stagger x:24->0 delay 0.18+i*0.07 dur .4; CTA buttons
  full-width py-3.5 rounded-full.
- Hero content (max-w 1280px relative z-10, pt clamp(40,8vw,72) pb 48; inner max-w 660 centered):
  H1 font-heading clamp(1.65rem,5vw,3rem) line-height 1.05 ls -.01em color text, centered,
  two lines with inline Lucide icons (Zap, LockKeyhole on line 1; Fingerprint on line 2),
  icons inline vertical-align middle top -2px margin 0 4px. Subtext font-body
  clamp(.9rem,2.5vw,1.1rem) text@0.8 max-w 560 lh 1.65. CTA pill radius 50px bg #7342E2
  white clamp(.9,2vw,1rem) padding 17px 24px min-w 210 shadow 0 4px 24px rgba(115,66,226,.28),
  justify-between gap 32, label "Get It Free" + ArrowRightCircle 20px, hover scale 1.04
  brightness 1.1, tap .96.
- Shared fadeUp variant: hidden{opacity:0,y:28}; visible(i)=>{opacity:1,y:0,
  transition:{delay:i*0.15,duration:0.6,ease:[0.22,1,0.36,1]}}.
""",
    "jack-3d-creator-portfolio": r"""
"Jack — 3D Creator" portfolio (React + TS + Tailwind + Framer Motion + Lucide).
Dark #0C0C0C, font Kanit 300-900. Global reset. .hero-heading = gradient text
linear-gradient(180deg,#646973,#BBCCD7) with -webkit-background-clip:text +
text-fill-color transparent. Main wrapper overflowX clip.
Sections: Hero, Marquee, About, Services, Projects.
- HERO h-screen: navbar 4 links About/Price/Projects/Contact (justify-between, #D7E2EA,
  uppercase tracking-wider, text-sm md:text-lg lg:text-[1.4rem]). Massive h1 "hi, i'm jack"
  .hero-heading font-black uppercase leading-none whitespace-nowrap, text-[14vw]..lg:[17.5vw].
  Bottom bar justify-between items-end: left small uppercase paragraph max-w[160-260],
  right ContactButton. Hero portrait centered absolute using Magnet (mouse-follow,
  padding 150 strength 3, active "transform .3s ease-out", inactive ".6s ease-in-out"),
  img w-[280..520]. FadeIn stagger by element.
- MARQUEE: two rows of GIF tiles (420x270 rounded-2xl object-cover) scrolling on page
  scroll; row1 moves right translateX(offset-200), row2 left; offset=(scrollY-sectionTop+
  innerHeight)*0.3; willChange transform; passive listener.
- ABOUT min-h-screen: 4 decorative 3D images absolutely in corners with FadeIn (x ±80).
  Heading "About me" .hero-heading clamp(3rem,12vw,160px). AnimatedText char-by-char
  scroll opacity 0.2->1 (useScroll offset ['start 0.8','end 0.2']). ContactButton below.
- SERVICES bg #FFFFFF rounded-t-[40-60px]: heading "Services" #0C0C0C clamp(3,12vw,160px).
  5 items (01 3D Modeling … 05 Web Design): horizontal — giant number clamp(3,10vw,140px)
  left + name (uppercase clamp(1,2.2vw,2.1rem)) and description (font-light opacity .6)
  right; 1px borders rgba(12,12,12,.15); staggered FadeIn i*0.1.
- PROJECTS bg #0C0C0C rounded-t, -mt-10..14 z-10: heading "Project" .hero-heading.
  3 sticky-stacking cards (useScroll+useTransform), each sticky top-24 in h-[85vh],
  targetScale=1-(total-1-i)*0.03, offset top i*28px; rounded-[40-60] border-2 #D7E2EA;
  top row number+category+name+LiveProject ghost button; bottom 2-col image grid
  (40% two stacked / 60% one tall) heavy radius.
- Components: ContactButton (gradient linear-gradient(123deg,#18011F,#B600A8 37%,
  #7621B0 72%,#BE4C00), inset shadows, white outline -3px offset, uppercase tracking-widest,
  label "Contact Me"); LiveProjectButton (ghost outline #D7E2EA, hover bg/10);
  FadeIn (whileInView once, ease [0.25,0.1,0.25,1], x/y props); Magnet; AnimatedText.
""",
    "prisma-creative-studio": r"""
"Prisma" creative studio (React + Vite + TS + Tailwind + Framer Motion + Lucide).
Dark/cinematic, warm cream. Fonts Almarai (300/400/700/800 global) + Instrument Serif
(italic accent). tailwind extend colors.primary #DEDBC8; fontFamily.serif Instrument Serif.
Bg black; About card #101010; Features cards #212121. Primary text #E1E0CC.
Two SVG noise utilities via feTurbulence data URIs: .noise-overlay (baseFreq .85 octaves 3,
on hero video), .bg-noise (baseFreq .9 octaves 4, Features bg).
Sections Hero/About/Features.
- HERO h-screen p-4 md:p-6 inset, inner rounded-2xl/[2rem] overflow-hidden. Bg video
  (CloudFront mp4) object-cover; .noise-overlay opacity .7 mix-blend-overlay; gradient
  from-black/30 via-transparent to-black/60. Navbar: black pill hanging from top
  (bg-black rounded-b-2xl/3xl px-4 py-2 md:px-8), 5 links Our story/Collective/Workshops/
  Programs/Inquiries (text-[10px]..md:text-sm, gap 3..14, color rgba(225,224,204,.8) hover #E1E0CC).
  Hero content bottom: 12-col grid (8 heading / 4 text+button). Giant "Prisma" via
  WordsPullUp text-[26vw]..xl:[19vw] font-medium leading-[.85] tracking-[-.07em] #E1E0CC,
  superscript * on final "a" (absolute top-[.65em] -right-[.3em] text-[.31em]); words slide
  up y:20 stagger .08 on useInView. Description right col (text-primary/70) fade up y:20
  delay .5 ease [0.16,1,0.3,1]. CTA "Join the lab" bg-primary rounded-full black text +
  black circle w-9/10 with ArrowRight; hover gap+scale; fade up delay .7.
- ABOUT bg-black, inner card #101010 max-w-6xl centered. Label "Visual arts". Heading via
  WordsPullUpMultiStyle 3 segments: "I am Marcus Chen," (font-normal), "a self-taught
  director." (italic font-serif Instrument Serif), "I have skills in color grading, visual
  effects, and narrative design." (font-normal); text-3xl..xl:7xl leading-[.95]. Body
  paragraph with scroll-linked per-character opacity (AnimatedLetter, useScroll offset
  ['start 0.8','end 0.2'], charProgress = i/total, range [cp-.1, cp+.05]).
- FEATURES min-h-screen bg-black + .bg-noise opacity .15. Header WordsPullUpMultiStyle
  2 lines (cream + gray). 4-col card grid (lg:h-[480px]) staggered scale .95->1 + fade
  useInView once margin -100px stagger .15 ease [0.22,1,0.36,1]. Card1 full video bg
  (CloudFront mp4) bottom text. Cards 2-4 bg #212121: small image icon, title+number,
  checklist (Check icon text-primary, text-gray-400), "Learn more" + ArrowRight rotated -45deg.
- Components: WordsPullUp (split words, slide y:20->0 stagger, useInView once, optional
  superscript *); WordsPullUpMultiStyle (per-segment className, inline-flex flex-wrap);
  AnimatedLetter (scroll char opacity reveal).
""",
    "velorah-video-hero": r"""
"Velorah®" cinematic video hero (React + Vite + Tailwind + TS + shadcn/ui).
- Fullscreen <video> autoPlay loop muted playsInline, CloudFront mp4, absolute inset-0
  w-full h-full object-cover z-0.
- Fonts Instrument Serif (display) + Inter 400/500; --font-display/--font-body vars;
  body var(--font-body), headings inline Instrument Serif.
- Dark HSL theme vars: --background 201 100% 13% (deep navy), --foreground 0 0% 100%,
  --muted-foreground 240 4% 66%, --primary 0 0% 100%/--primary-foreground 0 0% 4%,
  --secondary/--muted/--accent 0 0% 10%, --border/--input 0 0% 18%.
- Nav relative z-10 justify-between px-8 py-6 max-w-7xl mx-auto: logo "Velorah®"
  (® as <sup text-xs>) text-3xl Instrument Serif; md:flex links Home(active)/Studio/About/
  Journal/Reach Us (text-sm muted hover foreground); CTA "Begin Journey" liquid-glass
  rounded-full px-6 py-2.5 hover:scale-[1.03].
- Hero relative z-10 flex-col centered text-center px-6 pt-32 pb-40: H1 "Where dreams rise
  through the silence." text-5xl sm:text-7xl md:text-8xl leading-[.95] tracking-[-2.46px]
  max-w-7xl Instrument Serif, words "dreams" and "through the silence." in
  <em class="not-italic text-muted-foreground">. Subtext muted-foreground max-w-2xl mt-8.
  CTA "Begin Journey" liquid-glass rounded-full px-14 py-5 mt-12.
- .liquid-glass: bg rgba(255,255,255,.01) background-blend-mode luminosity, backdrop blur 4px,
  inset 0 1px 1px rgba(255,255,255,.1); ::before gradient border via padding 1.4px +
  linear-gradient(180deg, .45/.15/0/0/.15/.45) + -webkit-mask xor/exclude.
- @keyframes fade-rise (opacity 0 y24 -> 0); .animate-fade-rise (.8s), -delay (.2s),
  -delay-2 (.4s) on H1/subtext/CTA. Minimalist — no blobs/overlays; video provides depth.
""",
}
