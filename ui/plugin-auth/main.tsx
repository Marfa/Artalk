/* @refresh reload */
import './style.scss'
import type { ArtalkPlugin } from 'artalk'
import { DialogMain } from './DialogMain'
import { createLayer } from './lib/layer'
import { fetchMethods } from './lib/methods'
import { RenderEditorUser } from './EditorUser'
import type { AuthContext } from './types'

export const ArtalkAuthPlugin: ArtalkPlugin = (ctx) => {
  const editor = ctx.inject('editor')
  const api = ctx.inject('api')
  const apiHandlers = ctx.inject('apiHandlers')
  const user = ctx.inject('user')
  const events = ctx.inject('events')
  const config = ctx.inject('config')
  const layers = ctx.inject('layers')

  const authCtx: AuthContext = {
    getEditor: () => editor,
    getApi: () => api,
    getApiHandlers: () => apiHandlers,
    getUser: () => user,
    getEvents: () => events,
    getConf: () => config,
    getLayers: () => layers,
    $t: (key, args) => ctx.$t(key, args),
  }

  apiHandlers.add('need_auth_login', () => {
    openAuthDialog()
    throw new Error('Login required')
  })

  let anonymous = false
  let anonymousAllowed = false
  let $guestBtn: HTMLButtonElement | null = null

  const refreshBtn = () => {
    editor.getUI().$submitBtn.innerText =
      user.getData().token || anonymous
        ? authCtx.getConf().get().sendBtn || authCtx.$t('send')
        : authCtx.$t('signIn')
    refreshGuestBtn()
  }

  const refreshGuestBtn = () => {
    if (!$guestBtn) return
    const show = anonymousAllowed && !user.getData().token && !anonymous
    $guestBtn.style.display = show ? '' : 'none'
    $guestBtn.innerText = authCtx.$t('publishWithoutAuth')
  }

  const ensureGuestBtn = () => {
    if ($guestBtn) return
    const $submit = editor.getUI().$submitBtn
    const $wrap = $submit.parentElement
    if (!$wrap) return

    $guestBtn = document.createElement('button')
    $guestBtn.type = 'button'
    $guestBtn.className = 'atk-guest-btn'
    $guestBtn.innerText = authCtx.$t('publishWithoutAuth')
    $guestBtn.addEventListener('click', () => {
      onSkip()
    })
    $wrap.insertBefore($guestBtn, $submit)
  }

  authCtx.getConf().watchConf(['locale', 'sendBtn'], () => refreshBtn())
  authCtx.getEvents().on('user-changed', () => refreshBtn())

  authCtx.getEvents().on('mounted', () => {
    editor.getUI().$header.style.display = 'none'

    RenderEditorUser(authCtx)
    ensureGuestBtn()

    fetchMethods(api)
      .then((methods) => {
        anonymousAllowed = methods.some((m) => m.name === 'skip')
        refreshGuestBtn()
      })
      .catch(() => {
        anonymousAllowed = false
        refreshGuestBtn()
      })
  })

  const onSkip = () => {
    editor.getUI().$header.style.display = ''
    editor.getUI().$name.focus()
    ctx.updateConf({
      beforeSubmit: undefined,
    })

    anonymous = true
    refreshBtn()
  }

  const openAuthDialog = () => {
    createLayer(authCtx).show((layer) => (
      <DialogMain ctx={authCtx} onClose={() => layer.destroy()} onSkip={onSkip} />
    ))
  }

  ctx.updateConf({
    beforeSubmit: (editor, next) => {
      if (!user.getData().token) {
        openAuthDialog()
      } else {
        next()
      }
    },
  })
}
