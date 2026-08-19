import { sanitizeUrl } from '@/utils/url'

export function updateFavicon(logoUrl: string): void {
  const sanitizedLogoUrl = sanitizeUrl(logoUrl, {
    allowRelative: true,
    allowDataUrl: true,
  })
  if (!sanitizedLogoUrl) {
    return
  }

  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }

  const cleanUrl = sanitizedLogoUrl.split(/[?#]/, 1)[0].toLowerCase()
  if (cleanUrl.endsWith('.svg')) {
    link.type = 'image/svg+xml'
  } else if (cleanUrl.endsWith('.png')) {
    link.type = 'image/png'
  } else if (cleanUrl.endsWith('.webp')) {
    link.type = 'image/webp'
  } else if (cleanUrl.endsWith('.jpg') || cleanUrl.endsWith('.jpeg')) {
    link.type = 'image/jpeg'
  } else {
    link.type = 'image/x-icon'
  }
  link.href = sanitizedLogoUrl
}
