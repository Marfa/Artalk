import { describe, expect, it, vi } from 'vitest'
import { DataManager } from '@/data'
import type { CommentData, EventManager } from '@/types'

function makeComment(partial: Partial<CommentData> & { id: number }): CommentData {
  return {
    content: 'hi',
    nick: 'n',
    email_encrypted: 'x',
    link: '',
    rid: 0,
    ua: '',
    date: '2026-01-01 00:00:00',
    is_collapsed: false,
    is_pending: true,
    is_pinned: false,
    is_verified: false,
    is_allow_reply: true,
    page_key: '/p',
    visible: true,
    site_name: 'site',
    vote_up: 0,
    vote_down: 0,
    ...partial,
  }
}

describe('DataManager.updateComment', () => {
  it('updates existing comment and triggers comment-updated', () => {
    const trigger = vi.fn()
    const events = { trigger } as unknown as EventManager
    const data = new DataManager(events)
    data.loadComments([makeComment({ id: 1 })])
    trigger.mockClear()

    const next = makeComment({ id: 1, is_pending: false, content: 'ok' })
    data.updateComment(next)

    expect(data.getComments()).toHaveLength(1)
    expect(data.getComments()[0].is_pending).toBe(false)
    expect(trigger).toHaveBeenCalledWith('comment-updated', next)
  })

  it('upserts when comment id is missing from the list', () => {
    const trigger = vi.fn()
    const events = { trigger } as unknown as EventManager
    const data = new DataManager(events)

    const next = makeComment({ id: 9, is_pending: false })
    data.updateComment(next)

    expect(data.getComments()).toEqual([next])
    expect(trigger).toHaveBeenCalledWith('comment-updated', next)
  })
})
