export type StudySet = {
    id: string;
    title: string;
    createdAt: string;
    status: "READY" | "PROCESSING" | "FAILED";
    sourceType: "text" | "upload";
  };

export type QuizQuestion = {
  question: string;
  choices: string[];
  answerIndex: number;
  explanation?: string;
};

export type Quiz = { quiz: QuizQuestion[]; updatedAt: string };

export type QuizValidationResult = {
  questionIndex: number;
  isCorrect: boolean;
  correctAnswerIndex: number;
  userAnswerIndex: number | null;
  feedback?: string;
};

export type QuizValidation = {
  results: QuizValidationResult[];
  score: { correct: number; total: number; percentage: number };
};
  
