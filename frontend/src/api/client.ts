import type { Quiz, QuizValidation, StudySet } from "../types";

const STORAGE_KEYS = {
  studySets: "mock.studySets",
  studySetText: "mock.studySetText",
  quizzes: "mock.quizzes",
};

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL?.replace(/\/$/, "");

const useMock = !API_BASE_URL;

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const memoryStorage = (() => {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
  };
})();

const storage: StorageLike =
  typeof window !== "undefined" && window.localStorage
    ? window.localStorage
    : memoryStorage;

type StudySetTextStore = Record<string, string>;
type QuizStore = Record<string, Quiz>;

function delay() {
  const ms = 200 + Math.floor(Math.random() * 201);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = storage.getItem(key);
    if (!raw) {
      return fallback;
    }
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJSON<T>(key: string, value: T) {
  storage.setItem(key, JSON.stringify(value));
}

function extractWords(text: string) {
  return (text.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
    (word) => word.length >= 3
  );
}

function makeTitleFromText(text: string) {
  const words = extractWords(text).slice(0, 6);
  if (!words.length) {
  return "AI Quiz Builder";
  }
  return words
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getStores() {
  return {
    studySets: readJSON<StudySet[]>(STORAGE_KEYS.studySets, []),
    studySetText: readJSON<StudySetTextStore>(STORAGE_KEYS.studySetText, {}),
    quizzes: readJSON<QuizStore>(STORAGE_KEYS.quizzes, {}),
  };
}

function persistStores(stores: ReturnType<typeof getStores>) {
  writeJSON(STORAGE_KEYS.studySets, stores.studySets);
  writeJSON(STORAGE_KEYS.studySetText, stores.studySetText);
  writeJSON(STORAGE_KEYS.quizzes, stores.quizzes);
}

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `set_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

function ensureStudySetText(id: string) {
  const stores = getStores();
  return stores.studySetText[id] ?? "";
}

export async function createStudySetFromText(text: string, title?: string) {
  if (!useMock) {
    const res = await fetch(`${API_BASE_URL}/study-sets`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, title }),
    });
    if (!res.ok) {
      throw new Error("Failed to create study set.");
    }
    return (await res.json()) as StudySet;
  }

  await delay();
  const stores = getStores();
  const id = createId();
  const createdAt = new Date().toISOString();
  const studySet: StudySet = {
    id,
    title: title?.trim() || makeTitleFromText(text),
    createdAt,
    status: "READY",
    sourceType: "text",
  };

  stores.studySets.unshift(studySet);
  stores.studySetText[id] = text;
  persistStores(stores);

  return studySet;
}

export async function listStudySets() {
  if (!useMock) {
    const res = await fetch(`${API_BASE_URL}/study-sets`);
    if (!res.ok) {
      throw new Error("Failed to load study sets.");
    }
    return (await res.json()) as StudySet[];
  }

  await delay();
  const stores = getStores();
  return [...stores.studySets];
}

export async function getStudySet(id: string) {
  if (!useMock) {
    const res = await fetch(`${API_BASE_URL}/study-sets/${id}`);
    if (!res.ok) {
      return null;
    }
    return (await res.json()) as StudySet;
  }

  await delay();
  const stores = getStores();
  return stores.studySets.find((set) => set.id === id) ?? null;
}

export async function generateQuiz(studySetId: string) {
  if (!useMock) {
    const res = await fetch(`${API_BASE_URL}/study-sets/${studySetId}/quiz`, {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Failed to generate quiz.");
    }
    return (await res.json()) as Quiz;
  }

  await delay();
  const stores = getStores();
  const existing = stores.quizzes[studySetId];
  if (existing) {
    return existing;
  }
  const text = ensureStudySetText(studySetId);
  const words = extractWords(text);
  const uniqueWords = [...new Set(words)];
  const questions = uniqueWords.slice(0, 8).map((word, idx) => {
    const distractors = uniqueWords.filter((w) => w !== word).slice(0, 3);
    while (distractors.length < 3) {
      distractors.push(["concept", "element", "process"][distractors.length] ?? "term");
    }
    const answerIndex = idx % 4;
    const choices = [...distractors];
    choices.splice(answerIndex, 0, word);
    return {
      question: `Which of the following terms appears in the study text?`,
      choices,
      answerIndex,
      explanation: `"${word}" is present in the provided content.`,
    };
  });
  const quiz: Quiz = { quiz: questions, updatedAt: new Date().toISOString() };
  stores.quizzes[studySetId] = quiz;
  persistStores(stores);
  return quiz;
}

export async function validateQuiz(studySetId: string, answers: number[]) {
  if (!useMock) {
    const res = await fetch(`${API_BASE_URL}/study-sets/${studySetId}/validate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) {
      throw new Error("Failed to validate answers.");
    }
    return (await res.json()) as QuizValidation;
  }

  await delay();
  const stores = getStores();
  const quiz = stores.quizzes[studySetId];
  if (!quiz) {
    throw new Error("Quiz not found.");
  }
  let correct = 0;
  const results = quiz.quiz.map((q, index) => {
    const isCorrect = answers[index] === q.answerIndex;
    if (isCorrect) {
      correct += 1;
    }
    return {
      questionIndex: index,
      isCorrect,
      correctAnswerIndex: q.answerIndex,
      userAnswerIndex: answers[index] ?? null,
      feedback: q.explanation,
    };
  });
  return {
    results,
    score: {
      correct,
      total: quiz.quiz.length,
      percentage: quiz.quiz.length ? Math.round((correct / quiz.quiz.length) * 100) : 0,
    },
  };
}

export async function getPresignedUpload(filename: string, contentType: string) {
  if (useMock) {
    await delay();
    return { url: "", key: "" };
  }
  const res = await fetch(`${API_BASE_URL}/uploads/presign`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ filename, contentType }),
  });
  if (!res.ok) {
    throw new Error("Failed to start upload.");
  }
  return (await res.json()) as { url: string; key: string };
}

export async function createStudySetFromUpload(key: string, title?: string) {
  if (useMock) {
    throw new Error("Upload flow not available in mock mode.");
  }
  const res = await fetch(`${API_BASE_URL}/study-sets/from-upload`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ key, title }),
  });
  if (!res.ok) {
    throw new Error("Failed to create study set from upload.");
  }
  return (await res.json()) as StudySet;
}
