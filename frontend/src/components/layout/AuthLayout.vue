<template>
  <div class="auth-shell">
    <aside class="auth-visual" aria-hidden="true">
      <div class="window-scene">
        <span class="window-cloud window-cloud--one"></span>
        <span class="window-cloud window-cloud--two"></span>
        <span class="window-hill window-hill--one"></span>
        <span class="window-hill window-hill--two"></span>
        <span class="window-frame window-frame--vertical"></span>
        <span class="window-frame window-frame--horizontal"></span>
        <span class="window-sill"></span>
      </div>

      <div class="sakura-branch sakura-branch--visual">
        <span class="branch-twig branch-twig--one"></span>
        <span class="branch-twig branch-twig--two"></span>
        <span class="blossom blossom--one"></span>
        <span class="blossom blossom--two"></span>
        <span class="blossom blossom--three"></span>
        <span class="blossom blossom--four"></span>
      </div>

      <div class="mascot-message">
        <strong>欢迎回来</strong>
        <span>今天也要元气满满哦~</span>
      </div>

      <img
        src="/illustrations/nova-mascot.png"
        alt=""
        class="auth-mascot"
        width="1024"
        height="1536"
        loading="eager"
        decoding="async"
      />
    </aside>

    <main class="auth-content">
      <div class="auth-decorations" aria-hidden="true">
        <div class="sakura-branch sakura-branch--content">
          <span class="branch-twig branch-twig--one"></span>
          <span class="branch-twig branch-twig--two"></span>
          <span class="blossom blossom--one"></span>
          <span class="blossom blossom--two"></span>
          <span class="blossom blossom--three"></span>
          <span class="blossom blossom--four"></span>
        </div>

        <span class="falling-petal petal--one"></span>
        <span class="falling-petal petal--two"></span>
        <span class="falling-petal petal--three"></span>
        <span class="falling-petal petal--four"></span>
        <span class="falling-petal petal--five"></span>
        <span class="falling-petal petal--six"></span>
        <span class="falling-petal petal--seven"></span>
        <span class="falling-petal petal--eight"></span>
      </div>

      <div class="auth-note">
        <span class="auth-note__label">今日寄语</span>
        <p class="auth-note__text">
          愿每一次灵感，<br />
          都能被温柔接住。
        </p>
        <span class="auth-note__line" aria-hidden="true"></span>
        <p class="auth-note__caption">愿你今天也有好心情</p>
      </div>

      <div class="auth-panel">
        <slot />
      </div>

      <div class="mt-5 text-center text-sm">
        <slot name="footer" />
      </div>

      <div class="mt-7 text-center text-xs text-gray-400">
        &copy; {{ currentYear }} {{ siteName }}. All rights reserved.
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '@/stores'

const appStore = useAppStore()

const siteName = computed(() => appStore.siteName || 'Nove')
const currentYear = computed(() => new Date().getFullYear())

onMounted(() => {
  appStore.fetchPublicSettings()
})
</script>

<style scoped>
.auth-shell {
  min-height: 100vh;
  min-height: 100svh;
  overflow: hidden;
  background: #fcf1f2;
}

.auth-visual {
  display: none;
}

.auth-content {
  position: relative;
  isolation: isolate;
  display: flex;
  min-width: 0;
  min-height: 100vh;
  min-height: 100svh;
  flex-direction: column;
  justify-content: center;
  overflow-x: hidden;
  padding: 1.5rem 1rem;
}

.auth-decorations {
  display: none;
}

.auth-note {
  display: none;
}

.auth-panel {
  position: relative;
  z-index: 2;
  box-sizing: border-box;
  width: min(100%, 30rem);
  max-width: 30rem;
  margin: 0 auto;
  border: 1px solid #fbcfe8;
  border-radius: 8px;
  background: rgb(255 255 255 / 0.96);
  padding: 1.5rem;
  box-shadow: 0 18px 48px rgb(131 24 67 / 0.08);
}

.auth-content > :not(.auth-decorations) {
  position: relative;
  z-index: 2;
}

@media (min-width: 960px) {
  .auth-shell {
    display: grid;
    grid-template-columns: minmax(27rem, 0.88fr) minmax(32rem, 1.12fr);
  }

  .auth-visual {
    position: sticky;
    top: 0;
    display: flex;
    height: 100vh;
    min-height: 42rem;
    align-items: flex-end;
    justify-content: center;
    overflow: hidden;
    isolation: isolate;
    background: transparent;
  }

  .auth-mascot {
    position: relative;
    z-index: 3;
    width: min(94%, 46rem);
    height: 100%;
    object-fit: contain;
    object-position: center bottom;
  }

  .window-scene {
    position: absolute;
    z-index: 0;
    top: 7%;
    left: 6%;
    width: 88%;
    height: min(38vh, 23rem);
    overflow: hidden;
    border: 0.65rem solid rgb(255 255 255 / 0.82);
    background: #f9e9ef;
    box-shadow:
      0 0 0 1px rgb(224 151 177 / 0.2),
      0 18px 50px rgb(139 62 92 / 0.08);
  }

  .window-frame {
    position: absolute;
    z-index: 4;
    display: block;
    background: rgb(255 255 255 / 0.86);
    box-shadow: 0 0 0 1px rgb(224 151 177 / 0.12);
  }

  .window-frame--vertical {
    top: 0;
    bottom: 0;
    left: 52%;
    width: 0.5rem;
  }

  .window-frame--horizontal {
    top: 48%;
    right: 0;
    left: 0;
    height: 0.5rem;
  }

  .window-sill {
    position: absolute;
    z-index: 5;
    right: -1rem;
    bottom: 0;
    left: -1rem;
    height: 1rem;
    background: #fff;
    box-shadow: 0 -1px 0 rgb(224 151 177 / 0.18);
  }

  .window-cloud {
    position: absolute;
    z-index: 1;
    display: block;
    height: 1.2rem;
    border-radius: 999px;
    background: rgb(255 255 255 / 0.76);
  }

  .window-cloud::before,
  .window-cloud::after {
    position: absolute;
    bottom: 0;
    content: '';
    border-radius: 50%;
    background: inherit;
  }

  .window-cloud::before {
    left: 20%;
    width: 2.2rem;
    height: 2.2rem;
  }

  .window-cloud::after {
    right: 18%;
    width: 1.7rem;
    height: 1.7rem;
  }

  .window-cloud--one {
    top: 21%;
    left: 11%;
    width: 6.5rem;
  }

  .window-cloud--two {
    top: 14%;
    right: 8%;
    width: 5rem;
    opacity: 0.72;
  }

  .window-hill {
    position: absolute;
    bottom: 0;
    display: block;
    width: 68%;
    height: 43%;
    border-radius: 50% 50% 0 0;
  }

  .window-hill--one {
    left: -18%;
    background: #efc8d5;
  }

  .window-hill--two {
    right: -30%;
    bottom: -8%;
    background: #f3d4de;
  }

  .sakura-branch {
    position: absolute;
    pointer-events: none;
  }

  .sakura-branch::before {
    position: absolute;
    top: 47%;
    left: 2%;
    width: 94%;
    height: 43%;
    content: '';
    transform: rotate(-8deg);
    border-top: 0.36rem solid #ad7180;
    border-radius: 50%;
    opacity: 0.72;
  }

  .branch-twig {
    position: absolute;
    z-index: 1;
    display: block;
    width: 34%;
    height: 22%;
    border-top: 0.22rem solid #b77c89;
    border-radius: 50%;
    opacity: 0.72;
  }

  .branch-twig--one {
    top: 28%;
    left: 27%;
    transform: rotate(-29deg);
  }

  .branch-twig--two {
    top: 53%;
    left: 55%;
    transform: rotate(22deg);
  }

  .blossom {
    position: absolute;
    z-index: 2;
    display: block;
    width: 0.58rem;
    height: 0.58rem;
    border-radius: 50%;
    background: #ffe8ef;
    box-shadow:
      0.58rem 0 0 #f6a9c2,
      -0.58rem 0 0 #f9bfd1,
      0 0.58rem 0 #f7b3c9,
      0 -0.58rem 0 #fac6d6;
  }

  .blossom--one {
    top: 27%;
    left: 30%;
    transform: scale(1.05) rotate(12deg);
  }

  .blossom--two {
    top: 17%;
    left: 49%;
    transform: scale(0.78) rotate(-8deg);
  }

  .blossom--three {
    top: 48%;
    left: 65%;
    transform: scale(1.15) rotate(20deg);
  }

  .blossom--four {
    top: 58%;
    left: 81%;
    transform: scale(0.8) rotate(-14deg);
  }

  .sakura-branch--visual {
    z-index: 1;
    top: 1.5%;
    left: -7%;
    width: 66%;
    height: 20%;
    transform: rotate(-8deg);
    opacity: 0.82;
  }

  .mascot-message {
    position: absolute;
    z-index: 4;
    top: 24%;
    left: 63%;
    display: flex;
    width: min(30%, 13rem);
    min-width: 10rem;
    flex-direction: column;
    gap: 0.25rem;
    border: 1px solid rgb(241 157 190 / 0.8);
    border-radius: 8px;
    background: rgb(255 255 255 / 0.9);
    padding: 0.85rem 1rem;
    color: #6b334b;
    box-shadow: 0 12px 28px rgb(131 24 67 / 0.08);
  }

  .mascot-message::after {
    position: absolute;
    bottom: -0.45rem;
    left: 1.5rem;
    width: 0.8rem;
    height: 0.8rem;
    content: '';
    transform: rotate(45deg);
    border-right: 1px solid rgb(241 157 190 / 0.8);
    border-bottom: 1px solid rgb(241 157 190 / 0.8);
    background: rgb(255 255 255 / 0.9);
  }

  .mascot-message strong {
    font-size: 1rem;
    font-weight: 700;
  }

  .mascot-message span {
    color: #a2617a;
    font-size: 0.78rem;
    line-height: 1.5;
  }

  .auth-content {
    background: transparent;
    padding: 3rem clamp(2.5rem, 6vw, 6.5rem);
  }

  .auth-decorations {
    position: absolute;
    z-index: 0;
    inset: 0;
    display: block;
    overflow: hidden;
    pointer-events: none;
  }

  .auth-content > .auth-note {
    position: absolute;
    z-index: 1;
    top: 1rem;
    left: 50%;
    display: block;
    width: 25rem;
    max-width: calc(100% - 3rem);
    transform: translateX(-50%);
    color: #71354d;
    text-align: center;
    pointer-events: none;
  }

  .auth-note__label {
    display: block;
    margin-bottom: 0.45rem;
    color: #c46a8d;
    font-size: 0.8rem;
    font-weight: 700;
  }

  .auth-note__text {
    margin: 0;
    font-family: 'Noto Serif SC', 'Songti SC', SimSun, serif;
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.55;
  }

  .auth-note__line {
    display: block;
    width: 2.5rem;
    height: 1px;
    margin: 0.7rem auto 0.55rem;
    background: #e9a9bf;
  }

  .auth-note__caption {
    margin: 0;
    color: #a56d82;
    font-size: 0.78rem;
    line-height: 1.5;
  }

  .sakura-branch--content {
    top: -4rem;
    right: -5rem;
    width: min(32rem, 58vw);
    height: 19rem;
    transform: rotate(13deg);
    opacity: 0.48;
  }

  .falling-petal {
    position: absolute;
    top: -8%;
    left: var(--petal-x);
    display: none;
    width: var(--petal-size);
    aspect-ratio: 3 / 4;
    border-radius: 80% 0 80% 0;
    background: var(--petal-color);
    opacity: var(--petal-opacity);
  }

  .petal--one {
    --petal-x: 10%;
    --petal-size: 0.65rem;
    --petal-color: #f8b4cc;
    --petal-opacity: 0.58;
    --petal-drift: 4rem;
    --petal-mid-drift: -1.4rem;
    --petal-turn: 220deg;
    --petal-duration: 15s;
    --petal-delay: -2s;
  }

  .petal--two {
    --petal-x: 24%;
    --petal-size: 0.48rem;
    --petal-color: #fbc7d8;
    --petal-opacity: 0.5;
    --petal-drift: -3rem;
    --petal-mid-drift: 1rem;
    --petal-turn: -180deg;
    --petal-duration: 18s;
    --petal-delay: -11s;
  }

  .petal--three {
    --petal-x: 38%;
    --petal-size: 0.72rem;
    --petal-color: #f7a9c4;
    --petal-opacity: 0.46;
    --petal-drift: 5rem;
    --petal-mid-drift: -1.7rem;
    --petal-turn: 260deg;
    --petal-duration: 20s;
    --petal-delay: -6s;
  }

  .petal--four {
    --petal-x: 50%;
    --petal-size: 0.52rem;
    --petal-color: #fbd0dd;
    --petal-opacity: 0.55;
    --petal-drift: -4rem;
    --petal-mid-drift: 1.3rem;
    --petal-turn: -240deg;
    --petal-duration: 17s;
    --petal-delay: -14s;
  }

  .petal--five {
    --petal-x: 64%;
    --petal-size: 0.68rem;
    --petal-color: #f9b9cf;
    --petal-opacity: 0.48;
    --petal-drift: 3rem;
    --petal-mid-drift: -1rem;
    --petal-turn: 200deg;
    --petal-duration: 19s;
    --petal-delay: -9s;
  }

  .petal--six {
    --petal-x: 76%;
    --petal-size: 0.46rem;
    --petal-color: #fcd5e1;
    --petal-opacity: 0.56;
    --petal-drift: -5rem;
    --petal-mid-drift: 1.7rem;
    --petal-turn: -210deg;
    --petal-duration: 16s;
    --petal-delay: -4s;
  }

  .petal--seven {
    --petal-x: 87%;
    --petal-size: 0.6rem;
    --petal-color: #f8afc8;
    --petal-opacity: 0.42;
    --petal-drift: 2rem;
    --petal-mid-drift: -0.7rem;
    --petal-turn: 280deg;
    --petal-duration: 21s;
    --petal-delay: -15s;
  }

  .petal--eight {
    --petal-x: 95%;
    --petal-size: 0.5rem;
    --petal-color: #fac8d8;
    --petal-opacity: 0.5;
    --petal-drift: -3rem;
    --petal-mid-drift: 1rem;
    --petal-turn: -260deg;
    --petal-duration: 18s;
    --petal-delay: -7s;
  }

  .auth-panel {
    padding: 2rem;
  }
}

@media (min-width: 1600px) and (min-height: 850px) {
  .auth-content > .auth-note {
    top: 50%;
    left: 4%;
    width: 12rem;
    max-width: 12rem;
    transform: translateY(-50%);
    text-align: left;
  }

  .auth-note__line {
    margin-right: 0;
    margin-left: 0;
  }
}

@media (min-width: 960px) and (max-width: 1599px) and (max-height: 720px) {
  .auth-content > .auth-note {
    display: none;
  }
}

@media (prefers-reduced-motion: no-preference) {
  .auth-panel {
    animation: auth-panel-in 320ms ease-out both;
  }
}

@media (min-width: 960px) and (prefers-reduced-motion: no-preference) {
  .falling-petal {
    display: block;
    animation: petal-fall var(--petal-duration) var(--petal-delay) ease-in-out infinite;
  }
}

@keyframes auth-panel-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
}

@keyframes petal-fall {
  0% {
    transform: translate3d(0, -10vh, 0) rotate(0deg);
  }

  50% {
    transform: translate3d(var(--petal-mid-drift), 52vh, 0) rotate(120deg);
  }

  100% {
    transform: translate3d(var(--petal-drift), 116vh, 0) rotate(var(--petal-turn));
  }
}
</style>
