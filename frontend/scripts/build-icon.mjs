// Builds assets/brand/taleport.ico (16–256 px) from assets/brand/taleport-icon.svg,
// rendering every size straight from the vector so small sizes stay crisp.
// Also copies the SVG to public/favicon.svg for the UI.
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import sharp from 'sharp'

const here = dirname(fileURLToPath(import.meta.url))
const brand = resolve(here, '../../assets/brand')
const source = resolve(brand, 'taleport-icon.svg')
const SIZES = [16, 32, 48, 64, 128, 256]

const svg = await readFile(source)
const images = await Promise.all(
  SIZES.map((size) =>
    sharp(svg, { density: Math.max(72, (72 * size) / 256) * 4 })
      .resize(size, size)
      .png()
      .toBuffer(),
  ),
)

// ICO container with PNG-compressed entries (supported by Windows Vista and later).
const HEADER = 6
const ENTRY = 16
const header = Buffer.alloc(HEADER)
header.writeUInt16LE(0, 0) // reserved
header.writeUInt16LE(1, 2) // type: icon
header.writeUInt16LE(images.length, 4)

let offset = HEADER + ENTRY * images.length
const entries = images.map((png, i) => {
  const size = SIZES[i]
  const entry = Buffer.alloc(ENTRY)
  entry.writeUInt8(size >= 256 ? 0 : size, 0) // width (0 means 256)
  entry.writeUInt8(size >= 256 ? 0 : size, 1) // height
  entry.writeUInt8(0, 2) // palette colors
  entry.writeUInt8(0, 3) // reserved
  entry.writeUInt16LE(1, 4) // color planes
  entry.writeUInt16LE(32, 6) // bits per pixel
  entry.writeUInt32LE(png.length, 8)
  entry.writeUInt32LE(offset, 12)
  offset += png.length
  return entry
})

await writeFile(resolve(brand, 'taleport.ico'), Buffer.concat([header, ...entries, ...images]))
await writeFile(resolve(brand, 'taleport-256.png'), images.at(-1))
await mkdir(resolve(here, '../public'), { recursive: true })
await copyFile(source, resolve(here, '../public/favicon.svg'))
console.log(`taleport.ico written with sizes ${SIZES.join(', ')}`)
