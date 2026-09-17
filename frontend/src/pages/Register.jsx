import AuthLayout from "../layouts/AuthLayout";
import AuthForm from "../components/AuthForm";
export default function Register() {
  return (
    <AuthLayout>
      <AuthForm register />
    </AuthLayout>
  );
}
