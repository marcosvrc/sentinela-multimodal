import styles from "./States.module.css";

interface SkeletonProps {
  rows?: number;
}

export function Skeleton({ rows = 3 }: SkeletonProps) {
  return (
    <div aria-hidden="true" className={styles.skeletonWrapper}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className={styles.skeletonRow} />
      ))}
    </div>
  );
}
