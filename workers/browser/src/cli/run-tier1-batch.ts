import { executeTier1Batch, type Tier1BatchExecutionRequest } from "../batch-executor.js";

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function main(): Promise<void> {
  const rawInput = (await readStdin()).trim();
  if (!rawInput) {
    throw new Error("Tier 1 batch runner expected a JSON request on stdin.");
  }
  const request = JSON.parse(rawInput) as Tier1BatchExecutionRequest;
  const result = await executeTier1Batch(request);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
