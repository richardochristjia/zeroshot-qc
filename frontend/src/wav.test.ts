// @vitest-environment jsdom
import { expect, test } from 'vitest'
import { encodeWav } from './wav.ts'

function bytes(blob: Blob): Promise<DataView> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(new DataView(reader.result as ArrayBuffer))
    reader.readAsArrayBuffer(blob)
  })
}

test('encodeWav writes a PCM16 mono 16 kHz RIFF/WAVE header with the right data length', async () => {
  const view = await bytes(encodeWav(new Float32Array([0, 1, -1, 0.5]), 16000))
  const tag = (o: number): string => String.fromCharCode(...[0, 1, 2, 3].map((i) => view.getUint8(o + i)))
  expect([tag(0), tag(8), tag(12), tag(36)]).toEqual(['RIFF', 'WAVE', 'fmt ', 'data'])
  expect(view.byteLength).toBe(44 + 8)
  expect(view.getUint32(4, true)).toBe(36 + 8)
  expect(view.getUint16(20, true)).toBe(1) // PCM
  expect(view.getUint16(22, true)).toBe(1) // mono
  expect(view.getUint32(24, true)).toBe(16000)
  expect(view.getUint16(34, true)).toBe(16)
  expect(view.getUint32(40, true)).toBe(8)
  expect([view.getInt16(46, true), view.getInt16(48, true)]).toEqual([32767, -32768])
})
