import { createClient } from "@supabase/supabase-js";

// Note: In a real server environment, we would use process.env or import.meta.env
// and typically a service role key for admin privileges.
const supabaseUrl = process.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY || "placeholder-key";

export const supabaseAdmin = createClient(supabaseUrl, supabaseKey);
