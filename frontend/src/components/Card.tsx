// src/components/Card.tsx
import React from "react";
import "./Card.css";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
}

export const Card: React.FC<Props> = ({ title, children, ...rest }) => (
  <div className="card" {...rest}>
    {title && <h2 className="card-title">{title}</h2>}
    {children}
  </div>
);