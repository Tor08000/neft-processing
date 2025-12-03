import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

type QueryKey = unknown;

type Updater<TInput, TOutput> = TOutput | ((input: TInput) => TOutput);

type MutationFn<TData, TVariables> = (variables: TVariables) => Promise<TData> | TData;

type QueryFn<TData> = () => Promise<TData> | TData;

type PlaceholderFn<TData> = (previousData: TData | undefined) => TData | undefined;

type RefetchFn = () => Promise<void>;

type MutationSideEffect<TData, TVariables> = (data: TData, variables: TVariables) => void;

type QueryState<TData, TError> = {
  data: TData | undefined;
  error: TError | null;
  isLoading: boolean;
  isFetching: boolean;
  refetch: RefetchFn;
};

type MutationState<TError> = {
  error: TError | null;
  isPending: boolean;
};

class QueryClient {
  private cache = new Map<string, unknown>();

  private serializeKey(key: QueryKey): string {
    return typeof key === "string" ? key : JSON.stringify(key);
  }

  getQueryData<TData>(queryKey: QueryKey): TData | undefined {
    return this.cache.get(this.serializeKey(queryKey)) as TData | undefined;
  }

  setQueryData<TData>(queryKey: QueryKey, updater: Updater<TData | undefined, TData | undefined>): TData | undefined {
    const key = this.serializeKey(queryKey);
    const previous = this.cache.get(key) as TData | undefined;
    const next =
      typeof updater === "function" ? (updater as (input: TData | undefined) => TData | undefined)(previous) : updater;
    if (next !== undefined) {
      this.cache.set(key, next);
    } else {
      this.cache.delete(key);
    }
    return next;
  }

  invalidateQueries(): Promise<void> {
    return Promise.resolve();
  }
}

const QueryClientContext = createContext<QueryClient | null>(null);

const QueryClientProvider: React.FC<{ client: QueryClient; children?: React.ReactNode }> = ({ client, children }) => (
  <QueryClientContext.Provider value={client}>{children}</QueryClientContext.Provider>
);

function useQueryClient(): QueryClient {
  const client = useContext(QueryClientContext);
  return client ?? new QueryClient();
}

function useQuery<TData = unknown, TError = Error>({
  queryKey,
  queryFn,
  placeholderData,
}: {
  queryKey: QueryKey;
  queryFn: QueryFn<TData>;
  placeholderData?: PlaceholderFn<TData>;
}): QueryState<TData, TError> {
  const client = useQueryClient();
  const initialData = useMemo(() => placeholderData?.(client.getQueryData<TData>(queryKey)) ?? client.getQueryData<TData>(queryKey), [
    client,
    queryKey,
    placeholderData,
  ]);

  const [state, setState] = useState<QueryState<TData, TError>>({
    data: initialData,
    error: null,
    isLoading: !initialData,
    isFetching: false,
    refetch: async () => undefined,
  });

  const runQuery = async () => {
    setState((prev) => ({ ...prev, isFetching: true, error: null }));
    try {
      const data = await queryFn();
      client.setQueryData<TData>(queryKey, data);
      setState({ data, error: null, isLoading: false, isFetching: false, refetch: runQuery });
    } catch (error) {
      setState((prev) => ({ ...prev, error: error as TError, isLoading: false, isFetching: false }));
    }
  };

  useEffect(() => {
    if (state.data === undefined) {
      runQuery();
    }
  }, [queryKey]);

  return state;
}

function useMutation<TData = unknown, TError = Error, TVariables = void>({
  mutationFn,
  onSuccess,
}: {
  mutationFn: MutationFn<TData, TVariables>;
  onSuccess?: MutationSideEffect<TData, TVariables>;
}) {
  const [state, setState] = useState<MutationState<TError>>({ error: null, isPending: false });

  const mutate = (variables: TVariables) => {
    setState({ error: null, isPending: true });
    Promise.resolve(mutationFn(variables))
      .then((data) => {
        setState({ error: null, isPending: false });
        onSuccess?.(data, variables);
      })
      .catch((error) => {
        setState({ error: error as TError, isPending: false });
      });
  };

  return { mutate, error: state.error, isPending: state.isPending };
}

export { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient };
