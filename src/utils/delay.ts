export async function randomDelay(minSeconds: number = 1, maxSeconds: number = 3): Promise<void> {
  const delayMs = Math.random() * (maxSeconds - minSeconds) * 1000 + minSeconds * 1000;
  await new Promise((resolve) => setTimeout(resolve, delayMs));
}

export async function fixedDelay(seconds: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}

export async function delayMs(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}
