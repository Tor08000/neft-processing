import type React from "react";

type QueryKey = ReadonlyArray<unknown>;

type Updater<TInput, TOutput> = TOutput | ((input: TInput) => TOutput);

declare class QueryClient {
  constructor(config?: Record<string, unknown>);
  setQueryData<TData>(queryKey: QueryKey, updater: Updater<TData | undefined, TData | undefined>): void;
  invalidateQueries(options?: { queryKey?: QueryKey }): Promise<void>;
}

declare const QueryClientProvider: React.FC<{ client: QueryClient; children?: React.ReactNode }>;

declare interface UseQueryOptions<TData, TError = Error> {
  queryKey: QueryKey;
  queryFn: () => Promise<TData> | TData;
  placeholderData?: (previousData: TData | undefined) => TData | undefined;
  enabled?: boolean;
  staleTime?: number;
  refetchOnWindowFocus?: boolean;
  refetchOnMount?: boolean;
}

declare interface UseQueryResult<TData, TError = Error> {
  data: TData | undefined;
  error: TError | null;
  isLoading: boolean;
  isFetching: boolean;
  refetch: () => Promise<void>;
}

declare function useQuery<TData = unknown, TError = Error>(options: UseQueryOptions<TData, TError>): UseQueryResult<TData, TError>;

declare interface UseMutationOptions<TData, TError, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData> | TData;
  onSuccess?: (data: TData, variables: TVariables) => void;
}

declare interface UseMutationResult<TData, TError, TVariables> {
  mutate: (variables: TVariables) => void;
  isPending: boolean;
  error: TError | null;
}

declare function useMutation<TData = unknown, TError = Error, TVariables = void>(
  options: UseMutationOptions<TData, TError, TVariables>,
): UseMutationResult<TData, TError, TVariables>;

declare function useQueryClient(): QueryClient;

declare module "@tanstack/react-query" {
  export { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient };
}

export {};
