import type { Content } from "./types";
export const CATEGORY_MAP: Record<string, Record<string, string[]>> = {
  futurework: {
    Layoffs: ["layoff", "redundan"],
    Cybersecurity: ["cyber", "hack", "security"],
    Regulation: ["regulat", "law", "policy"],
    Earnings: ["earning", "revenue", "profit"],
    "AI & jobs": ["ai", "job", "work", "automat"],
  },
  tradewinds: {
    Sanctions: ["sanction", "embargo"],
    Energy: ["energy", "oil", "gas", "power"],
    Currencies: ["currency", "currencies", "dollar", "yuan", "forex"],
    "Supply chain": ["supply", "shipping", "logistics"],
    Chips: ["chip", "semiconductor"],
    Trade: ["trade", "tariff", "export", "import"],
  },
  escapevelocity: {
    "Mars/Moon": ["mars", "moon", "lunar"],
    "Telescopes/astronomy": [
      "telescope",
      "astronom",
      "galaxy",
      "webb",
      "stellar",
      "supernova",
      "black hole",
    ],
    Startups: ["startup", "start-up", "investment"],
    Policy: ["policy", "regulat", "budget"],
    Launches: ["launch", "rocket", "spacex", "orbit", "starship"],
  },
  tentongues: {
    "Food & drink": ["water", "food", "bread", "milk", "tea", "coffee", "rice", "egg", "fruit", "meat", "soup", "cheese"],
    People: ["mother", "father", "brother", "sister", "friend", "family", "baby", "child", "teacher", "doctor"],
    Home: ["house", "door", "window", "table", "chair", "bed", "kitchen", "key", "room"],
    Nature: ["sun", "moon", "star", "sky", "rain", "snow", "wind", "fire", "sea", "river", "mountain", "tree", "flower"],
    Travel: ["train", "bus", "car", "ticket", "map", "airport", "station", "road", "street", "city", "hotel"],
    Verbs: ["eat", "drink", "sleep", "walk", "run", "read", "write", "speak", "listen", "go", "come", "help", "learn", "love", "work"],
    Feelings: ["happy", "sad", "tired", "hungry", "thank", "sorry", "hello", "goodbye", "please"],
  },
};
export function category(
  c: Pick<Content, "channel" | "topic" | "title"> & { tags?: string[] | null },
): string {
  const text =
    `${c.topic} ${c.title} ${(c.tags ?? []).join(" ")}`.toLowerCase();
  return (
    Object.entries(CATEGORY_MAP[c.channel] ?? {}).find(([, words]) =>
      words.some((w) => new RegExp(`\\b${w}`, "i").test(text)),
    )?.[0] ?? "Other"
  );
}
export const categories = [
  ...new Set(Object.values(CATEGORY_MAP).flatMap(Object.keys)),
  "Other",
];
