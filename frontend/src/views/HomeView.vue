<template>
  <!-- Custom Home Content: Full Page Mode -->
  <div v-if="hasHomeContent" class="min-h-screen">
    <iframe
      v-if="isHomeContentUrl"
      :src="homeContent.trim()"
      class="h-screen w-full border-0"
      allowfullscreen
    ></iframe>
    <!-- SECURITY: homeContent is an admin-only setting. -->
    <div v-else v-html="homeContent"></div>
  </div>

  <!-- Compact Home Page -->
  <div
    v-else-if="compactHomeEnabled"
    data-testid="compact-home"
    class="flex min-h-screen flex-col bg-white text-rose-950"
  >
    <header class="border-b border-rose-100 px-4 py-4 sm:px-6">
      <nav class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 sm:gap-4">
        <div class="flex min-w-0 flex-1 items-center gap-3">
          <img
            :src="siteLogo || '/logo.svg'"
            alt="Logo"
            class="h-9 w-9 shrink-0 rounded-lg object-contain"
          />
          <span class="min-w-0 truncate text-base font-semibold">{{ siteName }}</span>
        </div>
        <div class="flex max-w-full shrink-0 flex-wrap items-center justify-end gap-2">
          <LocaleSwitcher />
          <a
            v-if="docUrl"
            :href="docUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-rose-500 transition-colors hover:bg-rose-50"
            :title="t('home.viewDocs')"
          >
            <Icon name="book" size="md" />
          </a>
          <router-link
            :to="isAuthenticated ? dashboardPath : '/login'"
            class="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700"
          >
            {{ isAuthenticated ? t('home.dashboard') : t('home.login') }}
          </router-link>
        </div>
      </nav>
    </header>

    <main class="flex min-w-0 flex-1 items-center justify-center px-4 py-16 sm:px-6">
      <div class="min-w-0 max-w-2xl text-center">
        <img
          :src="siteLogo || '/logo.svg'"
          alt="Logo"
          class="mx-auto mb-6 h-20 w-20 rounded-2xl object-contain"
        />
        <h1 class="[overflow-wrap:anywhere] text-3xl font-bold md:text-4xl">{{ siteName }}</h1>
        <p class="mt-4 whitespace-pre-wrap [overflow-wrap:anywhere] text-base text-rose-800/70">{{ siteSubtitle }}</p>
        <router-link
          :to="isAuthenticated ? dashboardPath : '/login'"
          class="mt-8 inline-flex min-h-10 items-center justify-center rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          {{ isAuthenticated ? t('home.goToDashboard') : t('home.login') }}
        </router-link>
      </div>
    </main>
  </div>

  <!-- Default Home Page -->
  <div v-else data-testid="default-home" class="home-page min-h-screen overflow-hidden bg-white text-rose-950">
    <header class="hidden">
      <nav class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:h-[72px] sm:px-6 lg:px-8">
        <router-link to="/home" class="flex min-w-0 items-center gap-3" aria-label="Home">
          <img
            :src="siteLogo || '/logo.svg'"
            alt="Logo"
            class="h-9 w-9 shrink-0 rounded-lg object-contain"
          />
          <span class="truncate text-base font-bold text-rose-950 sm:text-lg">{{ siteName }}</span>
        </router-link>

        <div class="hidden items-center gap-8 text-sm font-medium text-rose-900/70 md:flex">
          <a href="#models" class="transition-colors hover:text-primary-600">{{ t('home.nav.models') }}</a>
          <a href="#start" class="transition-colors hover:text-primary-600">{{ t('home.nav.howItWorks') }}</a>
          <a
            v-if="docUrl"
            :href="docUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="transition-colors hover:text-primary-600"
          >
            {{ t('home.docs') }}
          </a>
        </div>

        <div class="flex shrink-0 items-center gap-2 sm:gap-3">
          <LocaleSwitcher />
          <router-link
            v-if="!isAuthenticated"
            to="/login"
            class="hidden min-h-10 items-center px-2 text-sm font-semibold text-rose-900 transition-colors hover:text-primary-600 sm:inline-flex"
          >
            {{ t('home.login') }}
          </router-link>
          <router-link
            :to="primaryActionPath"
            class="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:bg-primary-700 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
          >
            {{ primaryActionLabel }}
            <Icon name="arrowRight" size="sm" :stroke-width="2" />
          </router-link>
        </div>
      </nav>
    </header>

    <main>
      <section class="hero-section relative">
        <div class="mx-auto grid min-h-screen max-w-7xl items-center gap-8 px-4 pb-14 pt-10 sm:px-6 sm:pb-16 sm:pt-14 lg:grid-cols-[minmax(0,1fr)_minmax(380px,0.86fr)] lg:gap-6 lg:px-8 lg:py-12">
          <div class="relative z-10 mx-auto max-w-2xl text-center lg:mx-0 lg:text-left">
            <div class="mb-6 inline-flex items-center gap-2 rounded-full border border-primary-200 bg-white px-4 py-2 text-sm font-semibold text-primary-700 shadow-sm">
              <Icon name="sparkles" size="sm" />
              <span>{{ t('home.heroEyebrow') }}</span>
            </div>

            <h1 class="hidden">
              {{ siteName }}
            </h1>
            <p class="mt-5 text-2xl font-semibold leading-snug text-rose-900 sm:text-3xl">
              {{ t('home.heroSubtitle') }}
            </p>
            <p class="mx-auto mt-5 max-w-xl text-base leading-8 text-rose-900/65 sm:text-lg lg:mx-0">
              {{ t('home.heroDescription') }}
            </p>

            <div class="mt-8 flex flex-col justify-center gap-3 sm:flex-row lg:justify-start">
              <router-link
                :to="primaryActionPath"
                class="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-primary-600 px-6 text-base font-semibold text-white shadow-lg shadow-primary-500/20 transition-all duration-200 hover:-translate-y-0.5 hover:bg-primary-700 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
              >
                {{ primaryActionLabel }}
                <Icon name="arrowRight" size="sm" :stroke-width="2" />
              </router-link>
              <router-link
                to="/model-plaza"
                class="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-rose-200 bg-white px-6 text-base font-semibold text-rose-900 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary-300 hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
              >
                <Icon name="grid" size="sm" />
                {{ t('home.viewModels') }}
              </router-link>
            </div>

            <div class="mt-9 grid grid-cols-3 gap-2 border-t border-rose-100 pt-6 sm:gap-4">
              <div v-for="benefit in benefits" :key="benefit.label" class="min-w-0 text-left">
                <div class="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                  <Icon :name="benefit.icon" size="sm" :stroke-width="2" />
                </div>
                <p class="text-xs font-semibold text-rose-950 sm:text-sm">{{ benefit.label }}</p>
                <p class="mt-1 hidden text-xs text-rose-900/55 sm:block">{{ benefit.detail }}</p>
              </div>
            </div>
          </div>

          <div class="hero-visual relative mx-auto h-[470px] w-full max-w-[560px] sm:h-[560px] lg:h-[650px]">
            <div class="absolute inset-x-[8%] bottom-[4%] top-[5%] rounded-[32%_32%_10%_10%/22%_22%_8%_8%] border border-primary-100 bg-primary-50/70"></div>

            <div class="message-bubble absolute left-0 top-[13%] z-20 max-w-[210px] rounded-lg border border-rose-100 bg-white px-4 py-3 shadow-lg shadow-rose-200/30 sm:left-[2%] lg:-left-[7%]">
              <div class="mb-1 flex items-center gap-2 text-xs font-bold text-primary-600">
                <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                NOVA ASSISTANT
              </div>
              <p class="text-sm font-medium leading-6 text-rose-950">{{ t('home.mascotGreeting') }}</p>
            </div>

            <div class="model-badge absolute right-0 top-[27%] z-20 flex items-center gap-2 rounded-lg border border-rose-100 bg-white px-3 py-2 shadow-lg shadow-rose-200/30 sm:right-[1%]">
              <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50 text-xs font-bold text-violet-600">AI</span>
              <div>
                <p class="text-xs font-bold text-rose-950">{{ t('home.modelReady') }}</p>
                <p class="text-[11px] text-rose-900/50">Claude · GPT · Gemini</p>
              </div>
            </div>

            <img
              src="/illustrations/nova-mascot.png"
              :alt="t('home.mascotAlt')"
              class="mascot-image absolute bottom-0 left-1/2 z-10 h-[96%] w-auto max-w-none -translate-x-1/2 object-contain object-bottom"
            />

            <div class="absolute bottom-[8%] right-[2%] z-20 hidden items-center gap-2 rounded-lg border border-rose-100 bg-white px-3 py-2 shadow-lg shadow-rose-200/30 sm:right-[8%] sm:flex">
              <Icon name="shield" size="sm" class="text-emerald-500" :stroke-width="2" />
              <span class="text-xs font-bold text-rose-950">{{ t('home.serviceOnline') }}</span>
            </div>
          </div>
        </div>
      </section>

      <section id="models" class="hidden">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="mx-auto max-w-2xl text-center">
            <p class="text-sm font-bold uppercase text-primary-600">{{ t('home.modelsEyebrow') }}</p>
            <h2 class="mt-3 text-3xl font-bold text-rose-950 sm:text-4xl">{{ t('home.providers.title') }}</h2>
            <p class="mt-4 text-base leading-7 text-rose-900/60">{{ t('home.modelsDescription') }}</p>
          </div>

          <div class="mt-10 grid gap-px overflow-hidden rounded-lg border border-rose-100 bg-rose-100 sm:grid-cols-2 lg:grid-cols-4">
            <div v-for="model in models" :key="model.name" class="group flex min-h-28 items-center gap-4 bg-white px-5 py-5 transition-colors hover:bg-primary-50/60">
              <div :class="model.accent" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-sm font-bold">
                {{ model.mark }}
              </div>
              <div class="min-w-0">
                <p class="truncate font-bold text-rose-950">{{ model.name }}</p>
                <p class="mt-1 text-xs text-rose-900/50">{{ t('home.providers.supported') }}</p>
              </div>
              <Icon name="checkCircle" size="sm" class="ml-auto shrink-0 text-emerald-500" :stroke-width="2" />
            </div>
          </div>
        </div>
      </section>

      <section id="start" class="hidden">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:items-end">
            <div>
              <p class="text-sm font-bold uppercase text-primary-600">{{ t('home.startEyebrow') }}</p>
              <h2 class="mt-3 text-3xl font-bold leading-tight text-rose-950 sm:text-4xl">{{ t('home.solutions.title') }}</h2>
              <p class="mt-4 max-w-md text-base leading-7 text-rose-900/60">{{ t('home.solutions.subtitle') }}</p>
              <router-link
                :to="primaryActionPath"
                class="mt-7 inline-flex min-h-11 items-center gap-2 font-semibold text-primary-700 transition-colors hover:text-primary-800"
              >
                {{ primaryActionLabel }}
                <Icon name="arrowRight" size="sm" :stroke-width="2" />
              </router-link>
            </div>

            <ol class="grid gap-4 sm:grid-cols-3">
              <li v-for="(step, index) in steps" :key="step.title" class="relative border-l-2 border-primary-200 bg-white px-5 py-6 shadow-sm">
                <span class="text-xs font-bold text-primary-500">0{{ index + 1 }}</span>
                <div class="mt-5 flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                  <Icon :name="step.icon" size="md" :stroke-width="2" />
                </div>
                <h3 class="mt-5 text-lg font-bold text-rose-950">{{ step.title }}</h3>
                <p class="mt-2 text-sm leading-6 text-rose-900/55">{{ step.description }}</p>
              </li>
            </ol>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useAppStore } from '@/stores'
import LocaleSwitcher from '@/components/common/LocaleSwitcher.vue'
import Icon from '@/components/icons/Icon.vue'
import { sanitizeUrl } from '@/utils/url'

type HomeIcon = 'sparkles' | 'shield' | 'chart' | 'userPlus' | 'key' | 'chatBubble'

const { t } = useI18n()
const authStore = useAuthStore()
const appStore = useAppStore()

const siteName = computed(() => appStore.cachedPublicSettings?.site_name || appStore.siteName || 'Sub2API Nova')
const siteLogo = computed(() => sanitizeUrl(appStore.cachedPublicSettings?.site_logo || appStore.siteLogo || '', { allowRelative: true, allowDataUrl: true }))
const siteSubtitle = computed(() => appStore.cachedPublicSettings?.site_subtitle || 'AI API Gateway Platform')
const docUrl = computed(() => sanitizeUrl(appStore.cachedPublicSettings?.doc_url || appStore.docUrl || ''))
const homeContent = computed(() => appStore.cachedPublicSettings?.home_content || '')
const hasHomeContent = computed(() => homeContent.value.trim().length > 0)
const compactHomeEnabled = computed(() => appStore.cachedPublicSettings?.compact_home_enabled === true)

const isHomeContentUrl = computed(() => {
  const content = homeContent.value.trim()
  return content.startsWith('http://') || content.startsWith('https://')
})

const isAuthenticated = computed(() => authStore.isAuthenticated)
const isAdmin = computed(() => authStore.isAdmin)
const dashboardPath = computed(() => isAdmin.value ? '/admin/dashboard' : '/dashboard')
const registrationEnabled = computed(() => appStore.cachedPublicSettings?.registration_enabled !== false)
const primaryActionPath = computed(() => {
  if (isAuthenticated.value) return dashboardPath.value
  return registrationEnabled.value ? '/register' : '/login'
})
const primaryActionLabel = computed(() => {
  if (isAuthenticated.value) return t('home.goToDashboard')
  return registrationEnabled.value ? t('home.freeRegister') : t('home.getStarted')
})

const benefits = computed<Array<{ icon: HomeIcon; label: string; detail: string }>>(() => [
  { icon: 'sparkles', label: t('home.benefits.multiModel'), detail: t('home.benefits.multiModelDesc') },
  { icon: 'shield', label: t('home.benefits.stable'), detail: t('home.benefits.stableDesc') },
  { icon: 'chart', label: t('home.benefits.transparent'), detail: t('home.benefits.transparentDesc') },
])

const models = [
  { name: 'Claude', mark: 'C', accent: 'bg-orange-50 text-orange-600' },
  { name: 'GPT', mark: 'G', accent: 'bg-emerald-50 text-emerald-600' },
  { name: 'Gemini', mark: 'G', accent: 'bg-blue-50 text-blue-600' },
  { name: 'Antigravity', mark: 'A', accent: 'bg-violet-50 text-violet-600' },
]

const steps = computed<Array<{ icon: HomeIcon; title: string; description: string }>>(() => [
  { icon: 'userPlus', title: t('home.steps.register.title'), description: t('home.steps.register.description') },
  { icon: 'key', title: t('home.steps.key.title'), description: t('home.steps.key.description') },
  { icon: 'chatBubble', title: t('home.steps.use.title'), description: t('home.steps.use.description') },
])

onMounted(() => {
  authStore.checkAuth()
  if (!appStore.publicSettingsLoaded) {
    appStore.fetchPublicSettings()
  }
})
</script>

<style scoped>
.hero-section {
  background: linear-gradient(90deg, rgba(253, 242, 248, 0.72) 0%, rgba(255, 255, 255, 0.96) 45%, rgba(253, 242, 248, 0.82) 100%);
}

.hero-visual::before {
  position: absolute;
  inset: 10% 3% 4%;
  content: '';
  border: 1px solid rgba(251, 207, 232, 0.8);
  border-radius: 48% 48% 12% 12% / 36% 36% 8% 8%;
}

.mascot-image {
  filter: drop-shadow(0 24px 24px rgba(190, 24, 93, 0.1));
}

.message-bubble,
.model-badge {
  animation: gentle-float 5s ease-in-out infinite;
}

.model-badge {
  animation-delay: -2.5s;
}

@keyframes gentle-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@media (max-width: 639px) {
  .message-bubble {
    top: auto;
    bottom: 23%;
    max-width: 175px;
  }

  .model-badge {
    top: auto;
    bottom: 7%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .message-bubble,
  .model-badge { animation: none; }
}
</style>
