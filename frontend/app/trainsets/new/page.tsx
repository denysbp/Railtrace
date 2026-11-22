import { apiGet, Line } from "@/lib/api";
import TrainsetForm from "@/components/TrainsetForm";

export default async function NewTrainsetPage() {
  const lines = await apiGet<Line[]>("/lines");
  return (
    <>
      <div className="page-head">
        <h1>Register a trainset</h1>
        <p>A trainset belongs to one home line and can only be assigned to that line&apos;s duties.</p>
      </div>
      <section className="card" style={{ maxWidth: 480 }}>
        <TrainsetForm lines={lines} />
      </section>
    </>
  );
}
