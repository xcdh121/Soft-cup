export const appendSseChunk = (buffer: string, chunk: string) => {
  const blocks = `${buffer}${chunk}`.split('\n\n')
  return {
    blocks,
    buffer: blocks.pop() ?? '',
  }
}
