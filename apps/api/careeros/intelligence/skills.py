"""Skills taxonomy: canonical names, categories, aliases and precise text matching.

Used by JD extraction (which skills a posting asks for), matching (does the profile cover
them) and the local embedder (so "k8s" and "Kubernetes" land on the same feature).

Ambiguous names that double as English words ("Go", "R", "C", "React", "Excel", ...) are
matched case-sensitively and, where needed, with custom patterns so that "go above and beyond"
or "R&D" are not mistaken for programming languages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache


class SkillCategory(StrEnum):
    PROGRAMMING_LANGUAGE = "PROGRAMMING_LANGUAGE"
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    MOBILE = "MOBILE"
    ML_AI = "ML_AI"
    DATA = "DATA"
    DATABASE = "DATABASE"
    CLOUD = "CLOUD"
    DEVOPS = "DEVOPS"
    TOOL = "TOOL"
    SECURITY = "SECURITY"
    SYSTEMS = "SYSTEMS"
    PRACTICE = "PRACTICE"
    SOFT = "SOFT"
    SPOKEN_LANGUAGE = "SPOKEN_LANGUAGE"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class SkillDef:
    name: str
    category: SkillCategory
    aliases: tuple[str, ...] = ()
    case_sensitive: bool = False
    pattern: str | None = None  # full custom regex replacing name/aliases matching


@dataclass(frozen=True, slots=True)
class SkillMatch:
    name: str
    category: SkillCategory
    start: int
    end: int
    matched_text: str


PL = SkillCategory.PROGRAMMING_LANGUAGE
FE = SkillCategory.FRONTEND
BE = SkillCategory.BACKEND
MO = SkillCategory.MOBILE
AI = SkillCategory.ML_AI
DA = SkillCategory.DATA
DB = SkillCategory.DATABASE
CL = SkillCategory.CLOUD
DO = SkillCategory.DEVOPS
TL = SkillCategory.TOOL
SE = SkillCategory.SECURITY
SY = SkillCategory.SYSTEMS
PR = SkillCategory.PRACTICE
SO = SkillCategory.SOFT
LA = SkillCategory.SPOKEN_LANGUAGE


def S(  # noqa: N802 - compact table constructor
    name: str,
    category: SkillCategory,
    *aliases: str,
    cs: bool = False,
    pattern: str | None = None,
) -> SkillDef:
    return SkillDef(name, category, aliases, cs, pattern)


_GO_NOT_VERB = (
    r"(?<![\w+#.\-])Go(?![\w+#\-])"
    r"(?!\s+(?:to|above|beyond|through|live|ahead|out|into|back|over|far|further|forward"
    r"|get|getter|the\s+extra)\b)"
)

SKILLS: tuple[SkillDef, ...] = (
    # --- Programming languages ---------------------------------------------------------
    S("Python", PL, "python3", "py"),
    S("Java", PL, "java8", "java 8", "java 11", "java 17", "java 21"),
    S("JavaScript", PL, "js", "ecmascript", "es6", "es2015"),
    S("TypeScript", PL),
    # "Series C funding" is not the C language.
    S("C", PL, pattern=r"(?<![\w+#.\-/])(?<!Series )(?<!series )C(?![\w+#\-])(?!\.\w)(?!\s*\+\+)"),
    S("C++", PL, "cpp", "c plus plus", "C++11", "C++14", "C++17", "C++20", "C++23"),
    S("C#", PL, "csharp", "c sharp"),
    S("Go", PL, "golang", pattern=_GO_NOT_VERB + r"|(?i:\bgolang\b)"),
    S("Rust", PL),
    S("Kotlin", PL),
    S("Swift", PL, cs=True),
    S("Objective-C", PL, "objective c", "objc"),
    S("Ruby", PL, cs=True),
    S("PHP", PL),
    S("Scala", PL),
    S("R", PL, pattern=r"(?<![\w+#.\-/'])R(?![\w+#&'\-/])(?!\s*&)(?!\.\w)"),
    S("MATLAB", PL, "matlab"),
    S("Julia", PL, cs=True),
    S("Perl", PL),
    S("Haskell", PL),
    S("Elixir", PL),
    S("Erlang", PL),
    S("Clojure", PL),
    S("F#", PL, "fsharp"),
    S("Dart", PL, cs=True),
    S("Lua", PL),
    S("Bash", PL, "shell scripting", "shell script", "bash scripting"),
    S("PowerShell", PL),
    S("SQL", PL, "t-sql", "pl/sql", "plsql"),
    S("Solidity", PL),
    S(
        "Assembly",
        PL,
        pattern=r"(?i:\b(?:x86|arm|mips|risc-v)\s+assembly\b|\bassembly\s+language\b)",
    ),
    S("Verilog", PL, "systemverilog"),
    S("VHDL", PL),
    S("CUDA", PL),
    S("OCaml", PL),
    S("Zig", PL),
    S("Fortran", PL),
    S("Groovy", PL),
    # --- Frontend ----------------------------------------------------------------------
    S("React", FE, "React.js", "ReactJS", "React JS", cs=True),
    S("Next.js", FE, "nextjs", "next js"),
    S("Vue.js", FE, "vue", "vuejs", "vue 3"),
    S("Nuxt", FE, "nuxt.js", "nuxtjs"),
    S("Angular", FE, "angularjs", "angular.js", cs=True),
    S("Svelte", FE, "sveltekit"),
    S("Redux", FE),
    S("Tailwind CSS", FE, "tailwind", "tailwindcss"),
    S("HTML", FE, "html5"),
    S("CSS", FE, "css3"),
    S("Sass", FE, "scss"),
    S("jQuery", FE),
    S("Bootstrap", FE),
    S("Webpack", FE),
    S("Vite", FE),
    S("Three.js", FE, "threejs"),
    S("WebGL", FE),
    S("D3.js", FE, "d3", "d3js"),
    S("Accessibility", FE, "a11y", "wcag"),
    # --- Backend -----------------------------------------------------------------------
    S("Node.js", BE, "nodejs", "node js", "Node", cs=False),
    S("Express", BE, "Express.js", "ExpressJS", cs=True),
    S("NestJS", BE, "nest.js"),
    S("Django", BE, "django rest framework", "drf"),
    S("Flask", BE, cs=True),
    S("FastAPI", BE, "fast api"),
    S("Spring Boot", BE, "springboot", "spring-boot"),
    # "Spring 2027 internship" is a season, not the framework.
    S(
        "Spring",
        BE,
        pattern=r"\bSpring\s+(?:Framework|MVC|Cloud|Security|Data|Batch)\b|(?i:\bspring framework\b)",
    ),
    S("Ruby on Rails", BE, "Rails", "RoR", cs=True),
    S("Laravel", BE),
    S(".NET", BE, "dotnet", "asp.net", "asp.net core", ".net core"),
    S("Gin", BE, "gin gonic", cs=True),
    S("Hibernate", BE),
    S("Celery", BE),
    S("GraphQL", BE),
    S("REST APIs", BE, "REST", "rest api", "restful", "restful api", "restful apis", "rest apis"),
    S("gRPC", BE, "protobuf", "protocol buffers"),
    S("WebSockets", BE, "websocket", "socket.io"),
    S(
        "Microservices",
        BE,
        "microservice",
        "micro-services",
        "service-oriented architecture",
        "soa",
    ),
    S("API Design", BE, "api development", "api design"),
    # --- Mobile ------------------------------------------------------------------------
    S("React Native", MO, "react-native"),
    S("Flutter", MO),
    S("SwiftUI", MO),
    S("Android", MO, "android sdk", "android development"),
    S("iOS", MO, "ios development", "ios sdk"),
    S("Jetpack Compose", MO),
    # "Career Expo" is an event; only the qualified forms mean the React Native toolchain.
    S("Expo", MO, pattern=r"(?i:\bexpo\s+(?:sdk|router|go)\b)"),
    # --- ML / AI -----------------------------------------------------------------------
    S("Machine Learning", AI, "ML", "machine-learning", pattern=None),
    S("Deep Learning", AI, "deep-learning", "neural networks", "neural network", "dnn"),
    S("Artificial Intelligence", AI, "AI", cs=False),
    S(
        "Natural Language Processing",
        AI,
        "nlp",
        "natural-language processing",
        "computational linguistics",
    ),
    S("Computer Vision", AI, "image processing", "object detection", "image recognition"),
    S("Reinforcement Learning", AI, "RL", "deep reinforcement learning"),
    S("Large Language Models", AI, "llm", "llms", "large language model", "foundation models"),
    S("Generative AI", AI, "genai", "gen ai", "generative models"),
    S("Retrieval-Augmented Generation", AI, "RAG", "retrieval augmented generation"),
    S("Prompt Engineering", AI, "prompting"),
    S(
        "Transformers",
        AI,
        "transformer models",
        "transformer architecture",
        "hugging face transformers",
    ),
    S("PyTorch", AI, "torch", "pytorch lightning"),
    S("TensorFlow", AI, "tensorflow 2", "tf2"),
    S("Keras", AI),
    S("JAX", AI, "flax", cs=True),
    S("scikit-learn", AI, "sklearn", "scikit learn", "scikit"),
    S("XGBoost", AI),
    S("LightGBM", AI),
    S("CatBoost", AI),
    S("Hugging Face", AI, "huggingface", "hf transformers"),
    S("LangChain", AI),
    S("LlamaIndex", AI, "llama index", "llama-index"),
    S("OpenCV", AI),
    S("spaCy", AI),
    S("NLTK", AI),
    S("MLOps", AI, "ml ops", "machine learning operations"),
    S("MLflow", AI),
    S("Kubeflow", AI),
    S("Weights & Biases", AI, "wandb", "weights and biases", "w&b"),
    S("ONNX", AI),
    S("TensorRT", AI),
    S("vLLM", AI),
    S("Recommender Systems", AI, "recommendation systems", "recommendation engine", "recsys"),
    S("Time Series Analysis", AI, "time series", "time-series", "forecasting"),
    S("Statistics", AI, "statistical modeling", "statistical analysis", "statistical modelling"),
    S("Probability", AI, "probability theory"),
    S("Linear Algebra", AI),
    S(
        "Mathematical Optimization",
        AI,
        "convex optimization",
        "operations research",
        "numerical optimization",
    ),
    S("Graph Neural Networks", AI, "gnn", "gnns", "graph neural network"),
    S("Diffusion Models", AI, "diffusion model", "stable diffusion"),
    S("Fine-tuning", AI, "fine tuning", "finetuning", "lora", "peft", "rlhf"),
    S("Speech Recognition", AI, "asr", "speech processing", "automatic speech recognition"),
    S("Information Retrieval", AI, "search ranking", "semantic search"),
    S("Vector Databases", AI, "vector database", "vector db", "vector search"),
    S("Federated Learning", AI),
    S("Causal Inference", AI),
    S("A/B Testing", AI, "ab testing", "a/b tests"),
    S(
        "Multimodal Learning",
        AI,
        "multimodal",
        "vision-language",
        "vision language models",
        "vlm",
        "vlms",
    ),
    S("AI Agents", AI, "agentic", "llm agents", "autonomous agents", "agent frameworks"),
    # --- Data --------------------------------------------------------------------------
    S("Pandas", DA),
    S("NumPy", DA),
    S("SciPy", DA),
    S("Matplotlib", DA),
    S("Seaborn", DA),
    S("Plotly", DA),
    S("Jupyter", DA, "jupyter notebook", "jupyter notebooks", "ipython"),
    S("Apache Spark", DA, "pyspark", "spark sql", "Spark", cs=False),
    S("Hadoop", DA, "hdfs", "mapreduce"),
    S("Apache Kafka", DA, "kafka"),
    S("Apache Airflow", DA, "airflow"),
    S("dbt", DA, "data build tool"),
    S("Snowflake", DA),
    S("BigQuery", DA, "big query"),
    S("Redshift", DA, "amazon redshift"),
    S("Databricks", DA),
    S("ETL", DA, "elt", "etl pipelines", "data pipelines", "data pipeline"),
    S("Data Engineering", DA),
    S("Data Analysis", DA, "data analytics"),
    S("Data Visualization", DA, "data visualisation", "dashboards", "dashboarding"),
    S("Data Science", DA),
    S("Tableau", DA),
    S("Power BI", DA, "powerbi"),
    S("Excel", DA, "Microsoft Excel", "MS Excel", cs=True),
    S("Looker", DA, cs=True),
    S("Apache Flink", DA, "flink"),
    S("Apache Beam", DA),
    S("Polars", DA),
    S("DuckDB", DA),
    # --- Databases ---------------------------------------------------------------------
    S("PostgreSQL", DB, "postgres", "psql", "postgresql"),
    S("MySQL", DB),
    S("SQLite", DB),
    S("MongoDB", DB, "mongo"),
    S("Redis", DB),
    S("Elasticsearch", DB, "elastic search", "elk stack", "opensearch"),
    S("Cassandra", DB, "apache cassandra"),
    S("DynamoDB", DB, "dynamo db"),
    S("Neo4j", DB, "graph databases", "graph database"),
    S("Oracle Database", DB, "oracle db", "oracle sql"),
    S("SQL Server", DB, "mssql", "microsoft sql server"),
    S("Firebase", DB, "firestore"),
    S("Supabase", DB),
    S("pgvector", DB),
    S("Pinecone", DB),
    S("Weaviate", DB),
    S("Milvus", DB),
    S("ChromaDB", DB, "chroma db"),
    S("ClickHouse", DB),
    S("NoSQL", DB, "no-sql"),
    # --- Cloud -------------------------------------------------------------------------
    S("AWS", CL, "amazon web services"),
    S("Google Cloud", CL, "gcp", "google cloud platform"),
    S("Microsoft Azure", CL, "azure"),
    S("AWS Lambda", CL, "Lambda", cs=False),
    S("Amazon S3", CL, "s3"),
    S("Amazon EC2", CL, "ec2"),
    S("Amazon SageMaker", CL, "sagemaker"),
    S("Amazon Bedrock", CL, "aws bedrock"),
    S("Vertex AI", CL, "vertexai"),
    S("Cloud Run", CL, "google cloud run"),
    S("Heroku", CL),
    S("Vercel", CL),
    S("Cloudflare", CL, "cloudflare workers"),
    S("Serverless", CL, "serverless architecture", "faas"),
    S(
        "Cloud Computing",
        CL,
        "cloud infrastructure",
        "cloud platforms",
        "cloud-native",
        "cloud native",
    ),
    # --- DevOps / infrastructure -------------------------------------------------------
    S("Docker", DO, "containers", "containerization", "containerisation", "dockerfile"),
    S("Kubernetes", DO, "k8s", "eks", "gke", "aks"),
    S("Terraform", DO),
    S("Ansible", DO),
    S("Helm", DO, cs=True),
    S("Jenkins", DO),
    S("GitHub Actions", DO, "gh actions"),
    S("GitLab CI", DO, "gitlab ci/cd", "gitlab-ci"),
    S(
        "CI/CD",
        DO,
        "ci cd",
        "cicd",
        "continuous integration",
        "continuous delivery",
        "continuous deployment",
    ),
    S("Linux", DO, "unix", "ubuntu", "debian", "centos", "rhel"),
    S("Nginx", DO),
    S("Prometheus", DO),
    S("Grafana", DO),
    S("Datadog", DO),
    S("Git", DO, "version control"),
    S("GitHub", TL),
    S("GitLab", TL),
    S("Observability", DO, "opentelemetry", "distributed tracing"),
    S("Site Reliability Engineering", DO, "SRE", "site reliability"),
    S("Infrastructure as Code", DO, "iac", "infrastructure-as-code"),
    S("Argo CD", DO, "argocd"),
    S("Istio", DO, "service mesh"),
    S("Pulumi", DO),
    S("Bazel", DO),
    S("CMake", DO),
    S("DevOps", DO, "dev ops"),
    # --- Tools / testing ---------------------------------------------------------------
    S("Jira", TL),
    S("Confluence", TL),
    S("Figma", TL),
    S("Postman", TL),
    S("Selenium", TL),
    S("Playwright", TL),
    S("Cypress", TL),
    S("Jest", TL, cs=True),
    S("pytest", TL, "py.test"),
    S("JUnit", TL),
    S("Storybook", TL),
    S(
        "Unit Testing",
        PR,
        "unit tests",
        "test automation",
        "automated testing",
        "integration testing",
    ),
    # --- Security ----------------------------------------------------------------------
    S("Cybersecurity", SE, "cyber security", "information security", "infosec"),
    S("Penetration Testing", SE, "pentesting", "pen testing", "ethical hacking"),
    S("Cryptography", SE, "encryption"),
    S("OAuth", SE, "oauth2", "oauth 2.0", "openid connect", "oidc"),
    S("OWASP", SE, "owasp top 10"),
    S("Network Security", SE),
    S("SIEM", SE),
    S("Burp Suite", SE),
    S("Wireshark", SE),
    S("Reverse Engineering", SE),
    S("Malware Analysis", SE),
    S("Application Security", SE, "appsec", "secure coding"),
    # --- Systems / CS fundamentals -----------------------------------------------------
    S("Algorithms", SY, "algorithm design", "competitive programming"),
    S("Data Structures", SY, "data structures and algorithms", "dsa"),
    S("Operating Systems", SY, "os internals"),
    S("Computer Networks", SY, "computer networking", "tcp/ip", "network protocols"),
    S("Distributed Systems", SY, "distributed computing"),
    S("System Design", SY, "systems design", "scalable systems", "software architecture"),
    S("Compilers", SY, "compiler design", "llvm"),
    S("Embedded Systems", SY, "firmware", "microcontrollers", "rtos"),
    S("Robotics", SY),
    S("ROS", SY, "robot operating system", "ros2"),
    S("FPGA", SY),
    S(
        "Parallel Computing",
        SY,
        "parallel programming",
        "multithreading",
        "concurrency",
        "openmp",
        "mpi",
    ),
    S("High Performance Computing", SY, "HPC"),
    S("Computer Architecture", SY),
    S("Blockchain", SY, "web3", "smart contracts", "ethereum"),
    S("Quantum Computing", SY, "qiskit"),
    S("Game Development", SY, "game dev", "gamedev"),
    S("Unity", SY, "Unity3D", cs=True),
    S("Unreal Engine", SY, "ue5", "unreal"),
    S("Signal Processing", SY, "dsp", "digital signal processing"),
    S("Control Systems", SY, "control theory"),
    # --- Practices -----------------------------------------------------------------------
    S("Agile", PR, "agile methodologies", "agile methodology"),
    S("Scrum", PR, "kanban"),
    S("Test-Driven Development", PR, "tdd", "test driven development"),
    S(
        "Object-Oriented Programming",
        PR,
        "oop",
        "object oriented programming",
        "object-oriented design",
        "ood",
    ),
    S("Functional Programming", PR),
    S("Design Patterns", PR),
    S("Code Review", PR, "code reviews"),
    S("Technical Writing", PR),
    S("Full Stack Development", PR, "full stack", "full-stack", "fullstack"),
    S("Backend Development", PR, "backend", "back-end", "server-side"),
    S("Frontend Development", PR, "frontend", "front-end", "client-side"),
    S("Web Development", PR, "web applications", "web apps"),
    S("Mobile Development", PR, "mobile apps", "mobile applications", "app development"),
    S("Product Management", PR, "product manager", "roadmapping"),
    S("UX Design", PR, "user experience", "ux research", "user research"),
    S("UI Design", PR, "user interface design", "interaction design"),
    S("Performance Optimization", PR, "performance tuning", "profiling"),
    # --- Soft skills ---------------------------------------------------------------------
    S("Communication", SO, "communication skills", "written communication", "verbal communication"),
    S("Leadership", SO, "team leadership", "led a team"),
    S("Teamwork", SO, "collaboration", "cross-functional collaboration", "team player"),
    S("Problem Solving", SO, "problem-solving", "analytical skills", "critical thinking"),
    S("Mentoring", SO, "mentorship", "coaching"),
    S("Public Speaking", SO, "presentation skills"),
    S("Project Management", SO, "program management"),
    S("Stakeholder Management", SO),
    # --- Spoken languages ----------------------------------------------------------------
    S("English", LA, cs=True),
    S("Hindi", LA, cs=True),
    S("Spanish", LA, cs=True),
    S("French", LA, cs=True),
    S("German", LA, cs=True),
    S("Mandarin", LA, "Chinese", cs=True),
    S("Japanese", LA, cs=True),
)

_LEFT = r"(?<![A-Za-z0-9_+#.\-])"
_RIGHT = r"(?![A-Za-z0-9_+#])"
_CASE_SENSITIVE_ALIASES = frozenset(
    {"AI", "ML", "RL", "RAG", "SRE", "HPC", "Node", "Spark", "Lambda", "RoR", "REST"}
)


def canonical_key(name: str) -> str:
    """Comparison key: lowercase, alphanumerics plus + and # ("Node.js" -> "nodejs")."""
    return re.sub(r"[^a-z0-9+#]", "", name.lower())


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, SkillDef], dict[str, SkillDef], re.Pattern[str]]:
    by_key: dict[str, SkillDef] = {}
    by_exact: dict[str, SkillDef] = {}
    insensitive: list[str] = []
    sensitive: list[str] = []
    custom: list[str] = []
    for skill in SKILLS:
        by_key.setdefault(canonical_key(skill.name), skill)
        for alias in skill.aliases:
            by_key.setdefault(canonical_key(alias), skill)
        if skill.pattern:
            custom.append(f"(?P<c{len(custom)}>{skill.pattern})")
            by_exact[f"__custom_{len(custom) - 1}"] = skill
            continue
        for term in (skill.name, *skill.aliases):
            if skill.case_sensitive or term in _CASE_SENSITIVE_ALIASES:
                sensitive.append(term)
                by_exact[term] = skill
            else:
                insensitive.append(term)
                by_exact[term.lower()] = skill
    # Longest first so "Spring Boot" wins over "Spring", "C++" over "C".
    insensitive.sort(key=len, reverse=True)
    sensitive.sort(key=len, reverse=True)
    parts = []
    if insensitive:
        joined = "|".join(re.escape(t) for t in insensitive)
        parts.append(f"(?P<i>(?i:{_LEFT}(?:{joined}){_RIGHT}))")
    if sensitive:
        joined = "|".join(re.escape(t) for t in sensitive)
        parts.append(f"(?P<s>{_LEFT}(?:{joined}){_RIGHT})")
    parts.extend(custom)
    pattern = re.compile("|".join(parts))
    return by_key, by_exact, pattern


def find_skills(text: str) -> list[SkillMatch]:
    """All skill mentions in `text`, in order of appearance (may contain repeats)."""
    by_key, by_exact, pattern = _index()
    matches: list[SkillMatch] = []
    for m in pattern.finditer(text):
        group = m.lastgroup
        matched = m.group(0)
        skill: SkillDef | None
        if group == "i":
            skill = by_exact.get(matched.lower()) or by_key.get(canonical_key(matched))
        elif group == "s":
            skill = by_exact.get(matched)
        elif group is not None and group.startswith("c"):
            skill = by_exact.get(f"__custom_{group[1:]}")
        else:
            skill = None
        if skill is not None:
            matches.append(SkillMatch(skill.name, skill.category, m.start(), m.end(), matched))
    return matches


def extract_skill_names(text: str) -> list[str]:
    """Distinct canonical skill names in order of first appearance."""
    seen: dict[str, None] = {}
    for match in find_skills(text):
        seen.setdefault(match.name, None)
    return list(seen)


def lookup(name: str) -> SkillDef | None:
    by_key, _, _ = _index()
    return by_key.get(canonical_key(name))


def normalize_skill_name(name: str) -> str:
    """Canonical display name for a known skill, otherwise the trimmed input."""
    skill = lookup(name)
    return skill.name if skill else " ".join(name.split())


def skill_category(name: str) -> SkillCategory:
    skill = lookup(name)
    return skill.category if skill else SkillCategory.OTHER
