import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { authService } from "../services/auth";
import Icon from "./Icon";

export default function AuthForm({ register = false }) {
  const [values, setValues] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const update = (event) => {
    const { name, value } = event.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: "" }));
    setError("");
  };

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const issues = {};
    if (register && !values.name.trim()) issues.name = "Enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim()))
      issues.email = "Enter a valid email address.";
    if (!values.password) issues.password = "Enter your password.";
    else if (register && values.password.length < 8)
      issues.password = "Use at least 8 characters.";
    if (register && values.confirm !== values.password)
      issues.confirm = "Your passwords do not match.";
    setErrors(issues);
    setError("");
    if (Object.keys(issues).length) return;
    setBusy(true);
    try {
      if (register) {
        await authService.register(values);
        navigate("/login", { replace: true, state: { registered: true } });
      } else {
        await login(values.email, values.password);
        // AuthLayout owns the redirect after the verified user is available.
      }
    } catch (err) {
      setErrors(err.fields || {});
      setError(
        err.status === 401
          ? "Invalid email or password. Please try again."
          : err.message,
      );
    } finally {
      setBusy(false);
    }
  }

  const field = (name, label, type, autoComplete, maxLength, hint) => (
    <div className="field" key={name}>
      <label htmlFor={name}>{label}</label>
      <div className={type === "password" ? "password-field" : undefined}>
        <input
          id={name}
          name={name}
          type={type === "password" && visible ? "text" : type}
          value={values[name]}
          onChange={update}
          autoComplete={autoComplete}
          maxLength={maxLength}
          required
          disabled={busy}
          aria-invalid={!!errors[name]}
          aria-describedby={
            errors[name] ? name + "-error" : hint ? name + "-hint" : undefined
          }
        />
        {name === "password" && (
          <button
            className="show-password"
            type="button"
            onClick={() => setVisible(!visible)}
            aria-label={visible ? "Hide password" : "Show password"}
            aria-pressed={visible}
          >
            {visible ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {errors[name] ? (
        <span className="field-error" id={name + "-error"}>
          {errors[name]}
        </span>
      ) : (
        hint && (
          <span className="field-hint" id={name + "-hint"}>
            {hint}
          </span>
        )
      )}
    </div>
  );

  return (
    <div className="auth-card">
      <span className="eyebrow">
        {register ? "MAKE SPACE FOR YOUR IDEAS" : "YOUR PLANNING WORKSPACE"}
      </span>
      <h2>{register ? "Create your account" : "Welcome back."}</h2>
      <p className="auth-intro">
        {register
          ? "A fresh canvas for everything you want to do."
          : "Sign in and pick up where you left off."}
      </p>
      {!register && location.state?.registered && (
        <div className="notice success" role="status">
          Account created. Sign in to open your workspace.
        </div>
      )}
      <form onSubmit={submit} noValidate aria-busy={busy}>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        {Object.values(errors).some(Boolean) && (
          <span className="sr-only" role="alert">
            Please correct the highlighted fields.
          </span>
        )}
        {register && field("name", "Full name", "text", "name", 100)}
        {field("email", "Email address", "email", "email", 320)}
        {field(
          "password",
          "Password",
          "password",
          register ? "new-password" : "current-password",
          1024,
          register
            ? "At least 8 characters. Make it unique to you."
            : undefined,
        )}
        {register &&
          field(
            "confirm",
            "Confirm password",
            "password",
            "new-password",
            1024,
          )}
        <button
          className="button primary auth-submit"
          type="submit"
          disabled={busy}
        >
          {busy ? (
            <>
              <span className="spinner" />
              {register ? "Creating account…" : "Signing in…"}
            </>
          ) : (
            <>
              {register ? "Create account" : "Sign in"}
              <Icon name="arrow" size={18} />
            </>
          )}
        </button>
      </form>
      <p className="auth-switch">
        {register ? "Already have an account?" : "New to ConstraintCanvas?"}{" "}
        <Link to={register ? "/login" : "/register"}>
          {register ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
