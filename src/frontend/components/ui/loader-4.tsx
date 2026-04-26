import styles from "./loader-4.module.css";

const DELAYS = [0, 1, 2, 1, 2, 2, 3, 3, 4] as const;

export default function Loader() {
  return (
    <div className={styles.loader} role="status" aria-label="Loading…">
      {DELAYS.map((d, i) => (
        <div
          key={i}
          className={`${styles.cell} ${d > 0 ? styles[`d${d}`] : ""}`}
        />
      ))}
    </div>
  );
}
