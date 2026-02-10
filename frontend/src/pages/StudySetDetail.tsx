import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import type { Quiz, QuizValidation, StudySet } from "../types";
import { generateQuiz, getStudySet, validateQuiz } from "../api/client";

export default function StudySetDetail() {
  const { id } = useParams();
  const studySetId = id ?? "";

  const [set, setSet] = useState<StudySet | null>(null);

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<number[]>([]);
  const [validation, setValidation] = useState<QuizValidation | null>(null);

  const [loadingSet, setLoadingSet] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoadingSet(true);
      const found = await getStudySet(studySetId);
      if (mounted) {
        setSet(found);
        setLoadingSet(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [studySetId]);

  const scoreText = useMemo(() => {
    if (!validation) return "";
    const { correct, total, percentage } = validation.score;
    return `${correct}/${total} (${percentage}%)`;
  }, [validation]);

  async function onGenerate() {
    setError(null);
    try {
      setWorking(true);
      const res = await generateQuiz(studySetId);
      setQuiz(res);
      setAnswers(new Array(res.quiz.length).fill(-1));
      setValidation(null);
    } catch {
      setError("Something went wrong generating the quiz.");
    } finally {
      setWorking(false);
    }
  }

  async function onValidate() {
    if (!quiz) {
      return;
    }
    setError(null);
    try {
      setWorking(true);
      const result = await validateQuiz(studySetId, answers);
      setValidation(result);
    } catch {
      setError("Something went wrong validating answers.");
    } finally {
      setWorking(false);
    }
  }

  if (loadingSet) return <Card>Loading...</Card>;
  if (!set)
    return (
      <Card>
        <p className="text-sm">
          Study set not found. Go back to <Link className="underline" to="/">Home</Link>.
        </p>
      </Card>
    );

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="mt-2 text-xl font-semibold">
          {set.title === "Untitled Study Set" ? "AI Quiz Builder" : set.title}
        </h1>
        <p className="text-sm text-gray-600">
          Created {new Date(set.createdAt).toLocaleString()} • Source: {set.sourceType}
        </p>
      </div>

      <Card>
        <div className="mt-4 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Generate a quiz for this study set.
          </div>
          <Button
            onClick={onGenerate}
            isLoading={working}
            disabled={working}
          >
            Generate quiz
          </Button>
        </div>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-4">
          <QuizView
            quiz={quiz}
            answers={answers}
            setAnswers={setAnswers}
            validation={validation}
          />
        </div>

        {quiz && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={onValidate} isLoading={working} disabled={working}>
              Submit answers
            </Button>
            {scoreText && (
              <span className="text-sm text-gray-600">Score: {scoreText}</span>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function QuizView({
  quiz,
  answers,
  setAnswers,
  validation,
}: {
  quiz: Quiz | null;
  answers: number[];
  setAnswers: (answers: number[]) => void;
  validation: QuizValidation | null;
}) {
  if (!quiz) return <p className="text-sm text-gray-600">No quiz yet. Click Generate quiz.</p>;

  return (
    <div className="grid gap-4">
      {quiz.quiz.map((q, idx) => {
        const result = validation?.results.find((r) => r.questionIndex === idx);
        return (
          <div key={idx} className="rounded-lg border border-gray-200 p-3">
            <div className="font-medium">
              {idx + 1}. {q.question}
            </div>
            <ul className="mt-2 grid gap-2 text-sm">
              {q.choices.map((choice, cIdx) => (
                <li key={cIdx} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={`q-${idx}`}
                    checked={answers[idx] === cIdx}
                    onChange={() => {
                      const next = [...answers];
                      next[idx] = cIdx;
                      setAnswers(next);
                    }}
                  />
                  <span>{choice}</span>
                </li>
              ))}
            </ul>
            {result && (
              <p className={`mt-2 text-xs ${result.isCorrect ? "text-green-600" : "text-red-600"}`}>
                {result.isCorrect ? "Correct" : "Incorrect"} • {result.feedback ?? "Review the quiz."}
              </p>
            )}
          </div>
        );
      })}
      <p className="text-xs text-gray-500">Updated: {new Date(quiz.updatedAt).toLocaleString()}</p>
    </div>
  );
}
