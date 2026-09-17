import { Link } from "react-router-dom";
import Icon from "../components/Icon";
export default function Placeholder({ title, icon = "layers" }) {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE</span>
          <h1>{title}</h1>
        </div>
      </div>
      <section className="placeholder-panel empty-state">
        <div className="empty-icon">
          <Icon name={icon} size={30} />
        </div>
        <span className="tag neutral">COMING LATER</span>
        <h2>A little more room to grow.</h2>
        <p>
          {title} is not available in this preview.
          <br />
          Your account and dashboard are ready to use.
        </p>
        <Link className="button secondary" to="/dashboard">
          <Icon name="grid" size={17} />
          Back to dashboard
        </Link>
      </section>
    </>
  );
}
