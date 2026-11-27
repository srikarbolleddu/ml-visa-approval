import {
  createHttpClient,
  createMockClient,
  type DemoClient,
  type DemoSample,
  type DemoSchema,
  type ExploreData,
  type Inputs,
  type Prediction,
} from "@srikarbolleddu/ml-demo-kit";
import fixture from "./fixture.json";

const samples = fixture.samples as DemoSample[];
const predictions = fixture.predictions as Prediction[];

/** Recorded prediction of whichever real example shares the most input values. */
function closestPrediction(inputs: Inputs): Prediction {
  let best = 0;
  let bestScore = -1;
  samples.forEach((sample, i) => {
    const score = Object.entries(sample.inputs).filter(
      ([k, v]) => inputs[k] === v,
    ).length;
    if (score > bestScore) [best, bestScore] = [i, score];
  });
  return predictions[best]!;
}

const apiUrl = import.meta.env.VITE_DEMO_API_URL as string | undefined;

/** The live API when configured at build time; otherwise responses recorded from it. */
export const isLive = Boolean(apiUrl);

export const client: DemoClient = apiUrl
  ? createHttpClient(apiUrl)
  : createMockClient(
      {
        schema: fixture.schema as DemoSchema,
        samples,
        explore: fixture.explore as ExploreData,
        predict: closestPrediction,
      },
      250,
    );
